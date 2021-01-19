#!/usr/bin/python3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".." / ".."))
sys.path.append(str(Path(__file__).parent / ".." / ".." / "unit_tests"))

from typing import *

from silicon import *
from test_utils import *
import inspect

TByte = Unsigned(length=8)

class Parity(Module):
    input = Input()
    output = Output(logic)

    def body(self):
        self.output = xor_gate(*self.input)

class Z80Alu(Module):
    in_a = Input(TByte)
    in_b = Input(TByte)
    in_f = Input(TByte)
    op = Input(Unsigned(length=7))
    op_8080_shift = Input(logic) # Set if 8008-style shift is to be performed. In this case, S Z and PV flags are not impacted
    out_l = Output(TByte)
    out_h = Output(TByte)
    out_f = Output(TByte)

    # These mostly come from instruction bits 5...3
    opArithBase = 0x00
    opADD = opArithBase + 0
    opADC = opArithBase + 1
    opSUB = opArithBase + 2
    opSBC = opArithBase + 3
    opAND = opArithBase + 4
    opXOR = opArithBase + 5
    opOR  = opArithBase + 6
    opCP  = opArithBase + 7

    # These mostly come from instruction bits 5...3 in the CB group
    opShiftBase = 0x20
    opRLC = opShiftBase + 0
    opRRC = opShiftBase + 1
    opRL  = opShiftBase + 2
    opRR  = opShiftBase + 3
    opSLA = opShiftBase + 4
    opSRA = opShiftBase + 5
    opSLL = opShiftBase + 6
    opSRL = opShiftBase + 7

    # Here bit-position is in bits 5...3, operation is in bits 7..6 in the CB group (0 is reserved for the shift group)
    opBitBase = 0x28
    opResBase = 0x30
    opSetBase = 0x38

    # These are other random operations we're going to need in the micro-code or some special instructions (maybe not all?)
    opIncDecBase = 0x40
    opMOV     = opIncDecBase + 0
    opINC     = opIncDecBase + 1
    opDEC     = opIncDecBase + 2

    opLargeBase = 0x48
    opMOV16   = opLargeBase + 0
    opINC16   = opLargeBase + 1
    opDEC16   = opLargeBase + 2
    opMOVZ16  = opLargeBase + 4 + 0
    opINCZ16  = opLargeBase + 4 + 1
    opDECZ16  = opLargeBase + 4 + 2

    opMiscBase = 0x50
    opSEH     = opMiscBase + 0 # sign-extend high byte -> second operand becomes 8 copies of fC
    opDAA     = opMiscBase + 1 # fixup for BCD after add/subtract
    opRLD     = opMiscBase + 2 # bit-wise element of RLD
    opRRD     = opMiscBase + 3 # bit-wise element of RRD
    opNEG     = opMiscBase + 4
    opCPL     = opMiscBase + 5
    opSCF     = opMiscBase + 6
    opCCF     = opMiscBase + 7

    flagC  = 0
    flagN  = 1
    flagPV = 2
    flagF3 = 3
    flagH  = 4
    flagF5 = 5
    flagZ  = 6
    flagS  = 7

    def body(self):
        # TODO: parity and zero calculation could be done in one place, instead of several, but oh, well...

        use_carry = self.op[0] & ~self.op[2] # Set for opADC and opSBC, clear for opADD and opSUB, also clear for opCP
        do_sub = self.op[1] | (self.op == self.opNEG)
        # Arithmetic group
        ########################
        # Add/sub sub-group
        # Do addition in three parts to get the half-carry and overflow detect bit
        carry_in = Select(self.op == self.opNEG,
            Select(self.op[6],
                Select(use_carry,
                    do_sub,
                    do_sub ^ self.in_f[self.flagC]
                ),
                self.op[0]
            ),
            1
        )
        a = Select(self.op == self.opNEG, self.in_a, 0)
        b = Select(self.op == self.opNEG, Select(self.op[6], self.in_b, 0), self.in_a)
        add_sub_lh = a[3:0] + Select(do_sub, b[3:0], ~b[3:0]) + carry_in
        add_sub_uh = a[6:4] + Select(do_sub, b[6:4], ~b[6:4]) + add_sub_lh[4]
        add_sub_msb_c = a[7] + Select(do_sub, b[7], ~b[7]) + add_sub_uh[3]
        add_sub_res = concat(add_sub_msb_c[0], add_sub_uh[2:0], add_sub_lh[3:0])
        add_sub_flags = concat(
            add_sub_res[7],                   # S
            add_sub_res == 0,                 # Z
            add_sub_res[5],                   # F5
            add_sub_lh[4] ^ do_sub,           # H
            add_sub_res[3],                   # F3
            add_sub_msb_c[1] ^ add_sub_uh[3], # PV (overflow in this case)
            do_sub,                           # N
            add_sub_msb_c[1] ^ do_sub         # C
        )
        # Logic sub-group
        logic_res = Select(self.op[1:0], self.in_a & self.in_b, self.in_a ^ self.in_b, self.in_a | self.in_b, self.in_a)
        logic_flags = concat(
            logic_res[7],                 # S
            logic_res == 0,               # Z
            logic_res[5],                 # F5
            ~(self.op[0] | self.op[1]),   # H
            logic_res[3],                 # F3
            Parity(logic_res),            # PV (parity in this case)
            "1'b0",                       # N
            "1'b0"                        # C
        )
        arith_sub_group_sel = self.op[2] & ~(self.op[1] & self.op[0])
        arith_res = Select(self.op[2], add_sub_res, logic_res) # We've already selected the right result for opCP into logic_res.
        arith_flags = Select(arith_sub_group_sel, add_sub_flags, logic_flags)

        # Shift group
        ######################
        shift_left_not_right = ~self.op[0]
        rotate_bit_in = Select(shift_left_not_right, self.in_a[0], self.in_a[7])
        shift_in = Select(self.op[2:1],
            rotate_bit_in,                              # RLC/RRC
            self.in_f[self.flagC],                           # RL/RR
            Select(self.op[0], "1'b0", self.in_a[7]),   # SLA/SRA
            ~self.op[0]                                 # SLL/SRL
        )
        shift_out = Select(shift_left_not_right, self.in_a[0], self.in_a[7])
        shift_res = Select(shift_left_not_right, concat(shift_in, self.in_a[7:1]), concat(self.in_a[6:0], shift_in))
        shift_parity = Parity(shift_res)
        shift_flags = concat(
            Select(self.op_8080_shift, shift_res[7], self.in_f[7]),      # S
            Select(self.op_8080_shift, shift_res == 0, self.in_f[6]),    # Z
            shift_res[5],                                                # F5
            "1'b0",                                                      # H
            shift_res[3],                                                # F3
            Select(self.op_8080_shift, shift_parity, self.in_f[2]),      # PV (parity in this case)
            "1'b0",                                                      # N
            shift_out                                                    # C
        )

        # Bit test/set/reset group
        ######################
        bit_pos = self.op[2:0]
        bit = Select(bit_pos,
            self.in_a[0],
            self.in_a[1],
            self.in_a[2],
            self.in_a[3],
            self.in_a[4],
            self.in_a[5],
            self.in_a[6],
            self.in_a[7]
        )
        bit_mask = Select(bit_pos,
            "8'b00000001",
            "8'b00000010",
            "8'b00000100",
            "8'b00001000",
            "8'b00010000",
            "8'b00100000",
            "8'b01000000",
            "8'b10000000"
        )
        bit_test = self.in_a & bit_mask
        bit_test_res = bit_test[7] | bit_test[6] | bit_test[5] | bit_test[4] | bit_test[3] | bit_test[2] | bit_test[1] | bit_test[0]
        bit_res = Select(self.op[4:3],
            self.in_a, # Reserved, so doesn't matter
            self.in_a, # bit test
            self.in_a & ~bit_mask, # reset
            self.in_a | bit_mask # set
        )
        bit_flags = Select(self.op[4],
            concat(
                bit_test[7],                  # S
                ~bit_test_res,                # Z
                bit_test[5],                  # F5
                "1'b1",                       # H
                bit_test[3],                  # F3
                bit_test_res,                 # PV (parity in this case)
                "1'b0",                       # N
                self.in_f[0]                  # C
            ),
            self.in_f
        )

        def daa_correct_digit(digit, carry_in, sub_not_add):
            correction = Select(carry_in | (digit > 9), 0, 6)
            new_val = Select(sub_not_add, digit + correction, digit - correction)
            return new_val[4], new_val[3:0]

        # IncDec group
        ######################
        inc_dec_res = Select(self.op[1:0] == 0, add_sub_res, self.in_a)
        inc_dec_flags = Select(self.op[1:0] == 0, add_sub_flags, self.in_f)

        # Large group
        ######################
        large_in = concat(Select(self.op[3], "8'b0", self.in_b), self.in_a)
        large_res = Select(self.op[1:0], 
            large_in,
            (large_in + 1)[15:0],
            (large_in - 1)[15:0]
        )
        large_z = Select((self.op[1:0] == 0 ) | (~self.op[2]),
            large_res == 0,
            self.in_f[self.flagZ]
        )
        large_flags = concat(
            self.in_f[7],
            large_z,
            self.in_f[5:0]
        )

        # Misc group
        ######################
        daa_step_1_carry, daa_digit_1 = daa_correct_digit(self.in_a[3:0], self.in_f[self.flagH], self.in_f[self.flagN])
        daa_step_2_digit_in = self.in_a[7:4] + daa_step_1_carry
        daa_step_2_carry, daa_digit_2 = daa_correct_digit(daa_step_2_digit_in[3:0], self.in_f[self.flagC] | daa_step_2_digit_in[4], self.in_f[self.flagN])
        daa_res = concat(daa_digit_2, daa_digit_1)
        daa_flags = concat(
            daa_res[7],        # S
            daa_res == 0,      # Z
            daa_res[5],        # F5
            daa_step_1_carry,  # H
            daa_res[3],        # F3
            Parity(daa_res),   # PV (parity in this case)
            self.in_f[1],      # N
            daa_step_2_carry   # C
        )
        rxd_res = Select(self.op[0], concat(self.in_a[7:4], self.in_a[2:0], self.in_b, self.in_a[3]), concat(self.in_a[7:4], self.in_b[0], self.in_a[3:0], self.in_b[7:1]))
        rxd_res_high = rxd_res[15:8]
        rxd_flags = concat(
            rxd_res_high[7],        # S
            rxd_res_high == 0,      # Z
            rxd_res_high[5],        # F5
            "1'b0",                 # H
            rxd_res_high[3],        # F3
            Parity(rxd_res_high),   # PV (parity in this case)
            "1'b0",                 # N
            self.in_f[0]            # C
        )
        seh_res = concat(self.in_f[self.flagC], self.in_f[self.flagC], self.in_f[self.flagC], self.in_f[self.flagC], self.in_f[self.flagC], self.in_f[self.flagC], self.in_f[self.flagC], self.in_f[self.flagC])
        seh_flags = self.in_f

        xfc_res = self.in_a
        xfc_flags = concat(
            self.in_f[7],                              # S
            self.in_f[6],                              # Z
            self.in_f[5],                              # F5
            self.in_f[4],                              # H
            self.in_f[3],                              # F3
            self.in_f[2],                              # PV
            self.in_f[1],                              # N
            Select(self.op[0], "1'b1", ~self.in_f[0])  # C
        )
        cpl_res = ~self.in_a
        cpl_flags = concat(
            self.in_f[7],                              # S
            self.in_f[6],                              # Z
            self.in_f[5],                              # F5
            "1'b1",                                    # H
            self.in_f[3],                              # F3
            self.in_f[2],                              # PV
            "1'b1",                                    # N
            self.in_f[0]                               # C
        )

        misc_res = Select(self.op[2:0],
            concat(seh_res, seh_res),
            concat(daa_res, daa_res),
            rxd_res,
            rxd_res,
            concat(add_sub_res, add_sub_res),
            concat(cpl_res, cpl_res),
            concat(xfc_res, xfc_res),
            concat(xfc_res, xfc_res)
        )
        misc_flags = Select(self.op[2:0],
            seh_flags,
            daa_flags,
            rxd_flags,
            rxd_flags,
            add_sub_flags,
            cpl_flags,
            xfc_flags,
            xfc_flags
        )



        # Final mux
        ####################
        self.out_l <<= Select(self.op[6:3],
            arith_res,      # 0x00
            arith_res,      # 0x08
            arith_res,      # 0x10
            arith_res,      # 0x18
            shift_res,      # 0x20
            bit_res,        # 0x28
            bit_res,        # 0x30
            bit_res,        # 0x38
            inc_dec_res,    # 0x40
            large_res[7:0], # 0x48
            misc_res[7:0]   # 0x50
        )

        self.out_h <<= Select(self.op[6:3],
            arith_res,       # 0x00
            arith_res,       # 0x08
            arith_res,       # 0x10
            arith_res,       # 0x18
            shift_res,       # 0x20
            bit_res,         # 0x28
            bit_res,         # 0x30
            bit_res,         # 0x38
            inc_dec_res,     # 0x40
            large_res[15:8], # 0x48
            misc_res[15:8]   # 0x50
        )

        self.out_f <<= Select(self.op[6:3],
            arith_flags,       # 0x00
            arith_flags,       # 0x08
            arith_flags,       # 0x10
            arith_flags,       # 0x18
            shift_flags,       # 0x20
            bit_flags,         # 0x28
            bit_flags,         # 0x30
            bit_flags,         # 0x38
            inc_dec_flags,     # 0x40
            large_flags,       # 0x48
            misc_flags         # 0x50
        )

def test_verilog():
    test.rtl_generation(Z80Alu, "z80_alu")

def test_sim():
    class Z80Alu_tb(Z80Alu):
        def simulate(self) -> TSimEvent:
            def str_to_flags(pattern: str) -> int:
                flags = 0
                if pattern.find("C") != -1:
                    flags |= 1 << self.flagC
                if pattern.find("N") != -1:
                    flags |= 1 << self.flagN
                if pattern.find("P") != -1:
                    flags |= 1 << self.flagPV
                if pattern.find("V") != -1:
                    flags |= 1 << self.flagPV
                if pattern.find("F3") != -1:
                    flags |= 1 << self.flagF3
                if pattern.find("H") != -1:
                    flags |= 1 << self.flagH
                if pattern.find("F5") != -1:
                    flags |= 1 << self.flagF5
                if pattern.find("Z") != -1:
                    flags |= 1 << self.flagZ
                if pattern.find("S") != -1:
                    flags |= 1 << self.flagS
                return flags
            def flags_to_str(flags: int) -> str:
                str_val = ""
                if flags & (1 << self.flagC) != 0:
                    str_val += "C"
                else:
                    str_val += "-"
                str_val += "|"
                if flags & (1 << self.flagN) != 0:
                    str_val += "N"
                else:
                    str_val += "-"
                str_val += "|"
                if flags & (1 << self.flagPV) != 0:
                    str_val += "PV"
                else:
                    str_val += "--"
                str_val += "|"
                if flags & (1 << self.flagF3) != 0:
                    str_val += "F3"
                else:
                    str_val += "--"
                str_val += "|"
                if flags & (1 << self.flagH) != 0:
                    str_val += "H"
                else:
                    str_val += "-"
                str_val += "|"
                if flags & (1 << self.flagF5) != 0:
                    str_val += "F5"
                else:
                    str_val += "--"
                str_val += "|"
                if flags & (1 << self.flagZ) != 0:
                    str_val += "Z"
                else:
                    str_val += "-"
                str_val += "|"
                if flags & (1 << self.flagS) != 0:
                    str_val += "S"
                else:
                    str_val += "-"
                return str_val
            def op_to_str(op: int) -> str:
                ops = {
                    self.opADD:      "opADD",
                    self.opADC:      "opADC",
                    self.opSUB:      "opSUB",
                    self.opSBC:      "opSBC",
                    self.opAND:      "opAND",
                    self.opXOR:      "opXOR",
                    self.opOR :      "opOR",
                    self.opCP :      "opCP",
                    self.opRLC:      "opRLC",
                    self.opRRC:      "opRRC",
                    self.opRL :      "opRL",
                    self.opRR :      "opRR",
                    self.opSLA:      "opSLA",
                    self.opSRA:      "opSRA",
                    self.opSLL:      "opSLL",
                    self.opSRL:      "opSRL",
                    self.opMOV:      "opMOV",
                    self.opINC:      "opINC",
                    self.opDEC:      "opDEC",
                    self.opMOV16:    "opMOV16",
                    self.opINC16:    "opINC16",
                    self.opDEC16:    "opDEC16",
                    self.opMOVZ16:   "opMOVZ16",
                    self.opINCZ16:   "opINCZ16",
                    self.opDECZ16:   "opDECZ16",
                    self.opSEH:      "opSEH",
                    self.opDAA:      "opDAA",
                    self.opRLD:      "opRLD",
                    self.opRRD:      "opRRD",
                    self.opNEG:      "opNEG",
                    self.opCPL:      "opCPL",
                    self.opSCF:      "opSCF",
                    self.opCCF:      "opCCF"
                }
                if op in ops:
                    return ops[op]
                if op & 0x38 == self.opBitBase:
                    return f"opBIT{op & 7}"
                if op & 0x38 == self.opResBase:
                    return f"opRES{op & 7}"
                if op & 0x38 == self.opSetBase:
                    return f"opSET{op & 7}"
                return f"UNK{op}"

            def _test_add_sub(a, b, c, add_not_sub, use_carry, do_compare, *, do_inc_dec: bool=False):
                sign_bit = lambda x: (0, 1)[x < 0]
                def to_sign(a):
                    if a > 127:
                        return a - 256
                    else:
                        return a

                if add_not_sub:
                    if use_carry:
                        if do_inc_dec:
                            op = self.opINC
                        else:
                            op = self.opADC
                        ex_r = (a + b + c) & 0xff
                        ex_c = (a + b + c) >> 8
                        ex_s = ((a + b + c) >> 7) & 1
                        ex_h = (((a & 15) + (b & 15) + c) >> 4) & 1
                        ex_v = int(sign_bit(to_sign(a) + to_sign(b) + c) != ex_r >> 7)
                    else:
                        op = self.opADD
                        ex_r = (a + b) & 0xff
                        ex_c = (a + b) >> 8
                        ex_s = ((a + b) >> 7) & 1
                        ex_h = (((a & 15) + (b & 15)) >> 4) & 1
                        ex_v = int(sign_bit(to_sign(a) + to_sign(b)) != ex_r >> 7)
                else:
                    if use_carry:
                        if do_inc_dec:
                            op = self.opDEC
                        else:
                            op = self.opSBC
                        ex_r = (a - b - c) & 0xff
                        ex_c = (((a - b - c) >> 8) & 1)
                        ex_s = ((a - b - c) >> 7) & 1
                        ex_h = (((a & 15) - (b & 15) - c) >> 4) & 1
                        ex_v = int(sign_bit(to_sign(a) - to_sign(b) - c) != ex_r >> 7)
                    else:
                        if do_compare:
                            op = self.opCP
                        else:
                            op = self.opSUB
                        ex_r = (a - b) & 0xff
                        ex_c = (((a - b) >> 8) & 1)
                        ex_s = ((a - b) >> 7) & 1
                        ex_h = (((a & 15) - (b & 15)) >> 4) & 1
                        ex_v = int(sign_bit(to_sign(a) - to_sign(b)) != ex_r >> 7)
                
                print(f"testing {op_to_str(op)}({a:3},{b:3} with C={c:1})... ", end="")
                self.in_a = a
                self.in_b = b
                if do_inc_dec:
                    self.in_f = str_to_flags("")
                else:
                    self.in_f = str_to_flags("") | (c * (1 << self.flagC))
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                if do_compare:
                    assert self.out_h.sim_value == a
                    assert self.out_l.sim_value == a
                else:
                    assert self.out_h.sim_value == ex_r
                    assert self.out_l.sim_value == ex_r
                assert (self.out_f.sim_value >> self.flagC)  & 1 == ex_c
                assert (self.out_f.sim_value >> self.flagN)  & 1 != add_not_sub
                assert (self.out_f.sim_value >> self.flagPV) & 1 == ex_v
                assert (self.out_f.sim_value >> self.flagH)  & 1 == ex_h
                assert (self.out_f.sim_value >> self.flagZ)  & 1 == (ex_r == 0)
                assert (self.out_f.sim_value >> self.flagS)  & 1 == ex_s
                print(f" passed")

            def test_add(a, b, c):
                yield from _test_add_sub(a,b,c,True,False,False)
            def test_adc(a, b, c):
                yield from _test_add_sub(a,b,c,True,True,False)
            def test_sub(a, b, c):
                yield from _test_add_sub(a,b,c,False,False,False)
            def test_cp(a, b, c):
                yield from _test_add_sub(a,b,c,False,False,True)
            def test_sbc(a, b, c):
                yield from _test_add_sub(a,b,c,False,True,False)

            def parity(a):
                p = 0
                for bit in range(8):
                    p ^= (a >> bit) & 1
                return p

            def _test_logical_flags(result, h, c):
                assert (self.out_f.sim_value >> self.flagC)  & 1 == c
                assert (self.out_f.sim_value >> self.flagN)  & 1 == 0
                assert (self.out_f.sim_value >> self.flagPV) & 1 == parity(result)
                assert (self.out_f.sim_value >> self.flagH)  & 1 == h
                assert (self.out_f.sim_value >> self.flagZ)  & 1 == (result == 0)
                assert (self.out_f.sim_value >> self.flagS)  & 1 == (result >> 7) & 1

            def _test_logic(a, b, set_flags, op, ex_r):
                print(f"testing {op_to_str(op)}({a:3},{b:3})... ", end="")
                self.in_a = a
                self.in_b = b
                if set_flags:
                    self.in_f = 255
                else:
                    self.in_f = 0
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r
                assert self.out_l.sim_value == ex_r
                _test_logical_flags(ex_r, op==self.opAND, 0)
                print(f" passed")

            def test_or(a, b, set_flags):
                op = self.opOR
                ex_r = (a & 255) | (b & 255)
                yield from _test_logic(a, b, set_flags, op, ex_r)
            
            def test_and(a, b, set_flags):
                op = self.opAND
                ex_r = (a & 255) & (b & 255)
                yield from _test_logic(a, b, set_flags, op, ex_r)

            def test_xor(a, b, set_flags):
                op = self.opXOR
                ex_r = (a & 255) ^ (b & 255)
                yield from _test_logic(a, b, set_flags, op, ex_r)

            def _test_mov_inc_dec(a, diff, flags):
                if diff == 0:
                    op = self.opMOV
                elif diff == 1:
                    op = self.opINC
                else:
                    op = self.opDEC
                ex_r = (a + diff) & 255
                ex_f = str_to_flags(flags)
                print(f"testing {op_to_str(op)}({a:3}, flags={flags_to_str(ex_f)})... ", end="")
                self.in_a = a
                self.in_b = a ^ 255 # just to set it to something different
                self.in_f = ex_f
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r
                assert self.out_l.sim_value == ex_r
                assert self.out_f.sim_value == ex_f
                print(f" passed")

            def test_mov(a, flags: str = ""):
                yield from _test_mov_inc_dec(a, 0, flags)
            def test_inc(a, flags: str = ""):
                yield from _test_add_sub(a, 0, 1, True, True, False, do_inc_dec=True)
                #yield from _test_mov_inc_dec(a, 1, flags)
            def test_dec(a, flags: str = ""):
                yield from _test_add_sub(a, 0, 1, False, True, False, do_inc_dec=True)
                #yield from _test_mov_inc_dec(a, -1, flags)

            def _test_mov_inc_dec_16(a, b, diff, generate_z, flags):
                if diff == 0:
                    if generate_z:
                        op = self.opMOVZ16
                    else:
                        op = self.opMOV16
                elif diff == 1:
                    if generate_z:
                        op = self.opINCZ16
                    else:
                        op = self.opINC16
                else:
                    if generate_z:
                        op = self.opDECZ16
                    else:
                        op = self.opDEC16
                ex_r = (a + (b << 8) + diff) & 0xffff
                in_f = str_to_flags(flags)
                if generate_z:
                    ex_f = (in_f & ~(1 << self.flagZ)) | int(ex_r == 0) << self.flagZ
                else:
                    ex_f = in_f
                print(f"testing {op_to_str(op)}({a:3}, {b:3}, flags={flags_to_str(in_f)})... ", end="")
                self.in_a = a
                self.in_b = b
                self.in_f = in_f
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r >> 8
                assert self.out_l.sim_value == ex_r & 0xff
                assert self.out_f.sim_value == ex_f
                print(f" passed")

            def test_mov16(a, b, flags: str = ""):
                yield from _test_mov_inc_dec_16(a, b, 0, False, flags)

            def test_movz16(a, b, flags: str = ""):
                yield from _test_mov_inc_dec_16(a, b, 0, True, flags)

            def test_inc16(a, b, flags: str = ""):
                yield from _test_mov_inc_dec_16(a, b, 1, False, flags)

            def test_incz16(a, b, flags: str = ""):
                yield from _test_mov_inc_dec_16(a, b, 1, True, flags)

            def test_dec16(a, b, flags: str = ""):
                yield from _test_mov_inc_dec_16(a, b, -1, False, flags)

            def test_decz16(a, b, flags: str = ""):
                yield from _test_mov_inc_dec_16(a, b, -1, True, flags)

            def _test_shift(a, c, left_not_right, logic_not_arith, shift_not_rotate, through_carry, mode_8080, *, flags: str = ""):
                if shift_not_rotate:
                    if logic_not_arith:
                        if left_not_right:
                            shift_in = 1
                        else:
                            shift_in = 0
                    else:
                        if left_not_right:
                            shift_in = 0
                        else:
                            shift_in = (a >> 7) & 1
                else:
                    if through_carry:
                        shift_in = c
                    else:
                        if left_not_right:
                            shift_in = (a >> 7) & 1
                        else:
                            shift_in = a & 1

                if left_not_right:
                    if shift_not_rotate:
                        if logic_not_arith:
                            op = self.opSLL
                        else:
                            op = self.opSLA
                    else:
                        if through_carry:
                            op = self.opRL
                        else:
                            op = self.opRLC
                    ex_r = a << 1 | shift_in
                    ex_c = (ex_r >> 8) & 1
                    ex_r &= 255
                else:
                    if shift_not_rotate:
                        if logic_not_arith:
                            op = self.opSRL
                        else:
                            op = self.opSRA
                    else:
                        if through_carry:
                            op = self.opRR
                        else:
                            op = self.opRRC
                    ex_r = a >> 1 | (shift_in << 7)
                    ex_c = (a >> 0) & 1
                    ex_r &= 255

                print(f"testing {op_to_str(op)}({a:3} with C={c:1})... ", end="")
                self.in_a = a
                self.in_b = a ^ 255
                self.in_f = str_to_flags(flags) | (c * (1 << self.flagC))
                self.op = op
                self.op_8080_shift = int(mode_8080)
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r
                assert self.out_l.sim_value == ex_r
                assert (self.out_f.sim_value >> self.flagC)  & 1 == ex_c
                assert (self.out_f.sim_value >> self.flagN)  & 1 == 0
                assert (self.out_f.sim_value >> self.flagH)  & 1 == 0
                if mode_8080:
                    assert (self.out_f.sim_value >> self.flagPV) & 1 == (self.in_f.sim_value >> self.flagPV) & 1
                    assert (self.out_f.sim_value >> self.flagZ)  & 1 == (self.in_f.sim_value >> self.flagZ)  & 1
                    assert (self.out_f.sim_value >> self.flagS)  & 1 == (self.in_f.sim_value >> self.flagS)  & 1
                else:
                    assert (self.out_f.sim_value >> self.flagPV) & 1 == parity(ex_r)
                    assert (self.out_f.sim_value >> self.flagZ)  & 1 == (ex_r == 0)
                    assert (self.out_f.sim_value >> self.flagS)  & 1 == (ex_r >> 7) & 1
                print(f" passed")

            def test_rlca(a, c, flags: str = ""):
                yield from _test_shift(a, c, True, None, False, False, True, flags=flags)
            def test_rla(a, c, flags: str = ""):
                yield from _test_shift(a, c, True, None, False, True, True, flags=flags)
            def test_rrca(a, c, flags: str = ""):
                yield from _test_shift(a, c, False, None, False, False, True, flags=flags)
            def test_rra(a, c, flags: str = ""):
                yield from _test_shift(a, c, False, None, False, True, True, flags=flags)
            def test_rlc(a, c):
                yield from _test_shift(a, c, True, None, False, False, False)
            def test_rl(a, c):
                yield from _test_shift(a, c, True, None, False, True, False)
            def test_rrc(a, c):
                yield from _test_shift(a, c, False, None, False, False, False)
            def test_rr(a, c):
                yield from _test_shift(a, c, False, None, False, True, False)
            def test_sll(a, c):
                yield from _test_shift(a, c, True, True, True, None, False)
            def test_sla(a, c):
                yield from _test_shift(a, c, True, False, True, None, False)
            def test_srl(a, c):
                yield from _test_shift(a, c, False, True, True, None, False)
            def test_sra(a, c):
                yield from _test_shift(a, c, False, False, True, None, False)

            def test_bit(a, bit, c):
                op = self.opBitBase | bit
                print(f"testing {op_to_str(op)}({a:3}, with C={c:1})... ", end="")
                ex_r = (a & 255) & (1 << bit)
                self.in_a = a
                self.in_b = a ^ 255
                self.in_f = c * (1 << self.flagC)
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == a
                assert self.out_l.sim_value == a
                _test_logical_flags(ex_r, 1, c)
                print(f" passed")

            def _test_set_res(a, bit, set_not_reset, flags: str):
                if set_not_reset:
                    op = self.opSetBase | bit
                    ex_r = a | (1 << bit)
                else:
                    op = self.opResBase | bit
                    ex_r = a & ~(1 << bit)
                ex_f = str_to_flags(flags)
                print(f"testing {op_to_str(op)}({a:3}) with flags {flags_to_str(ex_f)}... ", end="")
                self.in_a = a
                self.in_b = a ^ 255
                self.in_f = ex_f
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r
                assert self.out_l.sim_value == ex_r
                assert self.out_f.sim_value == ex_f
                print(f" passed")

            def test_set(a, bit, flags):
                yield from _test_set_res(a, bit, True, flags)

            def test_res(a, bit, flags):
                yield from _test_set_res(a, bit, False, flags)

            def test_seh(a, c, flags: str = ""):
                op = self.opSEH
                ex_f = str_to_flags(flags) & ~(1 << self.flagC) | (c << self.flagC)
                ex_r = 255 if c == 1 else 0
                print(f"testing {op_to_str(op)}({a:3}) with flags {flags_to_str(ex_f)}... ", end="")
                self.in_a = a
                self.in_b = a ^ 255
                self.in_f = ex_f
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r
                assert self.out_l.sim_value == ex_r
                assert self.out_f.sim_value == ex_f
                print(f" passed")

            def test_daa(a, n):
                op = self.opDAA
                dl = a & 0xf
                dh = (a >> 4) & 0xf
                diff = -6 if n else 6
                if dl > 9:
                    dl = (dl + diff) & 0x1f
                    h = dl > 15
                    dl &= 0xf
                else:
                    h = 0
                dh += int(h)
                if dh > 9:
                    dh = (dh + diff) & 0x1f
                    c = dh > 15
                    dh &= 0xf
                else:
                    c = 0
                ex_r = dl | (dh << 4)
                ex_h = h
                ex_c = c
                ex_n = n
                ex_z = ex_r == 0
                ex_s = (ex_r >> 7) & 1
                ex_p = parity(ex_r)
                in_f = n << self.flagN
                print(f"testing {op_to_str(op)}({a:3}) with flags {flags_to_str(in_f)}... ", end="")
                self.in_a = a
                self.in_b = a ^ 255
                self.in_f = in_f
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r
                assert self.out_l.sim_value == ex_r
                assert (self.out_f.sim_value >> self.flagC) & 1 == ex_c
                assert (self.out_f.sim_value >> self.flagH) & 1 == ex_h
                assert (self.out_f.sim_value >> self.flagZ) & 1 == ex_z
                assert (self.out_f.sim_value >> self.flagN) & 1 == ex_n
                assert (self.out_f.sim_value >> self.flagS) & 1 == ex_s
                assert (self.out_f.sim_value >> self.flagPV) & 1 == ex_p
                print(f" passed")

            def test_cpl(a, flags: str = ""):
                op = self.opCPL
                in_f = str_to_flags(flags)
                ex_r = a ^ 255
                ex_f = in_f | 1 << self.flagH | 1 << self.flagN
                print(f"testing {op_to_str(op)}({a:3}) with flags {flags_to_str(in_f)}... ", end="")
                self.in_a = a
                self.in_b = a ^ 255
                self.in_f = in_f
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r
                assert self.out_l.sim_value == ex_r
                assert self.out_f.sim_value == ex_f
                print(f" passed")

            def test_neg(a, flags: str = ""):
                op = self.opNEG
                in_f = str_to_flags(flags)
                ex_r = (-a) & 255
                ex_c = a != 0
                ex_n = 1
                ex_v = a == 0x80
                ex_h = (0 - (a & 0xf)) < 0
                ex_z = ex_r == 0
                ex_s = ex_r >> 7
                print(f"testing {op_to_str(op)}({a:3}) with flags {flags_to_str(in_f)}... ", end="")
                self.in_a = a
                self.in_b = a ^ 255
                self.in_f = in_f
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r
                assert self.out_l.sim_value == ex_r
                assert (self.out_f.sim_value >> self.flagC) & 1 == ex_c
                assert (self.out_f.sim_value >> self.flagH) & 1 == ex_h
                assert (self.out_f.sim_value >> self.flagZ) & 1 == ex_z
                assert (self.out_f.sim_value >> self.flagN) & 1 == ex_n
                assert (self.out_f.sim_value >> self.flagS) & 1 == ex_s
                assert (self.out_f.sim_value >> self.flagPV) & 1 == ex_v
                print(f" passed")

            def _test_carry(a, op, ex_c, flags: str = ""):
                in_f = str_to_flags(flags)
                ex_r = a
                ex_f = in_f & ~(1 << self.flagC) | (ex_c << self.flagC)
                print(f"testing {op_to_str(op)}({a:3}) with flags {flags_to_str(in_f)}... ", end="")
                self.in_a = a
                self.in_b = a ^ 255
                self.in_f = in_f
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r
                assert self.out_l.sim_value == ex_r
                assert self.out_f.sim_value == ex_f
                print(f" passed")

            def test_scf(a, flags: str = ""):
                yield from _test_carry(a, self.opSCF, 1, flags)
            
            def test_ccf(a, flags: str = ""):
                in_f = str_to_flags(flags)
                ex_c = 1 - ((in_f >> self.flagC) & 1)
                yield from _test_carry(a, self.opCCF, ex_c, flags)

            def test_rld(a, b, flags: str = ""):
                op = self.opRLD
                rot_in = (a & 0xf) << 8 | b
                in_f = str_to_flags(flags)
                ex_r = (a & 0xf0) << 8 | (rot_in << 1) & 0xfff | (rot_in >> 11)
                ex_s = (ex_r >> 8) >> 7
                ex_z = (ex_r >> 8) == 0
                ex_h = 0
                ex_p = parity(ex_r >> 8)
                ex_n = 0
                ex_c = (in_f >> self.flagC) & 1
                print(f"testing {op_to_str(op)}({a:3}, {b:3}) with flags {flags_to_str(in_f)}... ", end="")
                self.in_a <<= a
                self.in_b <<= b
                self.in_f <<= in_f
                self.op <<= op
                self.op_8080_shift <<= 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r >> 8
                assert self.out_l.sim_value == ex_r & 0xff
                assert (self.out_f.sim_value >> self.flagC) & 1 == ex_c
                assert (self.out_f.sim_value >> self.flagH) & 1 == ex_h
                assert (self.out_f.sim_value >> self.flagZ) & 1 == ex_z
                assert (self.out_f.sim_value >> self.flagN) & 1 == ex_n
                assert (self.out_f.sim_value >> self.flagS) & 1 == ex_s
                assert (self.out_f.sim_value >> self.flagPV) & 1 == ex_p
                print(f" passed")

            def test_rrd(a, b, flags: str = ""):
                op = self.opRRD
                rot_in = (a & 0xf) << 8 | b
                in_f = str_to_flags(flags)
                ex_r = (a & 0xf0) << 8 | (rot_in >> 1) & 0xfff | ((rot_in & 1) << 11)
                ex_s = (ex_r >> 8) >> 7
                ex_z = (ex_r >> 8) == 0
                ex_h = 0
                ex_p = parity(ex_r >> 8)
                ex_n = 0
                ex_c = (in_f >> self.flagC) & 1
                print(f"testing {op_to_str(op)}({a:3}, {b:3}) with flags {flags_to_str(in_f)}... ", end="")
                self.in_a = a
                self.in_b = b
                self.in_f = in_f
                self.op = op
                self.op_8080_shift = 0
                yield 10
                print(f" returned ({self.out_h.sim_value:3}, {self.out_l.sim_value:3}, {flags_to_str(self.out_f.sim_value)})", end="", flush=True)
                assert self.out_h.sim_value == ex_r >> 8
                assert self.out_l.sim_value == ex_r & 0xff
                assert (self.out_f.sim_value >> self.flagC) & 1 == ex_c
                assert (self.out_f.sim_value >> self.flagH) & 1 == ex_h
                assert (self.out_f.sim_value >> self.flagZ) & 1 == ex_z
                assert (self.out_f.sim_value >> self.flagN) & 1 == ex_n
                assert (self.out_f.sim_value >> self.flagS) & 1 == ex_s
                assert (self.out_f.sim_value >> self.flagPV) & 1 == ex_p
                print(f" passed")

            def directed_mist_tests():
                print("Directed misc tests")
                yield from test_rld(0x12, 0x34)
                yield from test_rrd(0x12, 0x34)
                yield from test_rld(0x12, 0x34, "C")
                yield from test_rrd(0x12, 0x34, "C")
                yield from test_rld(0xf2, 0x34)
                yield from test_rld(0xf1, 0x34)
                yield from test_rld(0x08, 0x34)
                yield from test_rrd(0xf2, 0x34)
                yield from test_rrd(0xf3, 0x34)
                yield from test_rrd(0x01, 0x34)
                yield from test_ccf(0x12, "C")
                yield from test_ccf(0x12, "V")
                yield from test_scf(0x12, "C")
                yield from test_scf(0x12, "V")
                yield from test_neg(0x00, "CH")
                yield from test_neg(0x80, "CH")
                yield from test_neg(0x7f, "CH")
                yield from test_neg(0xff, "CH")
                yield from test_neg(0xa4, "CH")
                yield from test_cpl(0x00, "CH")
                yield from test_cpl(0x80, "CH")
                yield from test_cpl(0x7f, "CH")
                yield from test_cpl(0xff, "CH")
                yield from test_cpl(0xa4, "CH")
                yield from test_scf(0xda, "CNH")
                yield from test_scf(0xda, "NH")
                yield from test_ccf(0xda, "CNH")
                yield from test_ccf(0xda, "NH")
                yield from test_daa(0x33, 0)
                yield from test_daa(0x33, 1)
                yield from test_daa(0x3a, 0)
                yield from test_daa(0x3a, 1)
                yield from test_daa(0xa3, 0)
                yield from test_daa(0xa3, 1)
                yield from test_daa(0xaa, 0)
                yield from test_daa(0xaa, 1)
                yield from test_daa(0x33, 0)
                yield from test_daa(0x33, 1)
                yield from test_daa(0x39, 0)
                yield from test_daa(0x39, 1)
                yield from test_daa(0x93, 0)
                yield from test_daa(0x93, 1)
                yield from test_daa(0x99, 0)
                yield from test_daa(0x99, 1)
                yield from test_daa(0x9a, 0)
                yield from test_daa(0x9a, 1)
                yield from test_seh(0xaa, 0, "NV")
                yield from test_seh(0xaa, 1, "NV")

            def directed_shift_tests():
                print("Directed shift tests")
                yield from test_rlca(3, 0, flags="PZS")
                yield from test_rla(3, 0, flags="PS")
                yield from test_rlca(11, 1, flags="S")
                yield from test_rla(11, 1, flags="ZS")
                yield from test_rlca(129, 0, flags="PZS")
                yield from test_rla(129, 0, flags="Z")
                yield from test_rlca(129, 1)
                yield from test_rla(129, 1)
                yield from test_rrca(3, 0)
                yield from test_rra(3, 0)
                yield from test_rrca(11, 1)
                yield from test_rra(11, 1)
                yield from test_rrca(129, 0)
                yield from test_rra(129, 0)
                yield from test_rrca(129, 1)
                yield from test_rra(129, 1)

                yield from test_rlc(3, 0)
                yield from test_rl(3, 0)
                yield from test_rlc(11, 1)
                yield from test_rl(11, 1)
                yield from test_rlc(129, 0)
                yield from test_rl(129, 0)
                yield from test_rlc(129, 1)
                yield from test_rl(129, 1)
                yield from test_rrc(3, 0)
                yield from test_rr(3, 0)
                yield from test_rrc(11, 1)
                yield from test_rr(11, 1)
                yield from test_rrc(129, 0)
                yield from test_rr(129, 0)
                yield from test_rrc(129, 1)
                yield from test_rr(129, 1)
                
                yield from test_sll(3, 1)
                yield from test_sla(3, 1)
                yield from test_srl(3, 1)
                yield from test_sra(3, 1)
                yield from test_sll(3, 0)
                yield from test_sla(3, 0)
                yield from test_srl(3, 0)
                yield from test_sra(3, 0)
                yield from test_sll(129, 1)
                yield from test_sla(129, 1)
                yield from test_srl(129, 1)
                yield from test_sra(129, 1)
                yield from test_sll(129, 0)
                yield from test_sla(129, 0)
                yield from test_srl(129, 0)
                yield from test_sra(129, 0)

            def directed_add_sub_tests():
                print("Directed add_sub tests")
                yield from test_add(0,0,0)
                yield from test_add(0,0,1)
                yield from test_sub(0,0,0)
                yield from test_sub(0,0,1)
                yield from test_add(3,4,0)
                yield from test_add(5,8,1)
                yield from test_adc(3,4,0)
                yield from test_adc(5,8,1)
                yield from test_sub(5,4,0)
                yield from test_sub(11,8,1)
                yield from test_sbc(5,4,0)
                yield from test_sbc(11,8,1)
                yield from test_add(128,127,0)
                yield from test_add(128,127,1)
                yield from test_adc(128,127,0)
                yield from test_adc(128,127,1)
                yield from test_add(240,240,0)

            def directed_cp_tests():
                print("Directed cp tests")
                yield from test_cp(3,4,0)
                yield from test_cp(5,8,1)
                yield from test_cp(3,4,0)
                yield from test_cp(5,8,1)
                yield from test_cp(5,4,0)
                yield from test_cp(11,8,1)
                yield from test_cp(5,4,0)
                yield from test_cp(11,8,1)
                yield from test_cp(128,127,0)
                yield from test_cp(128,127,1)
                yield from test_cp(128,127,0)
                yield from test_cp(128,127,1)
                yield from test_cp(240,240,0)

            def directed_bit_tests():
                print("Directed bit tests")
                yield from test_bit(0x00, 0, 0)
                yield from test_bit(0x00, 0, 1)
                yield from test_bit(0x01, 1, 0)
                yield from test_bit(0x03, 0, 1)
                yield from test_bit(0xff, 7, 0)
                yield from test_bit(0xaa, 6, 1)
                yield from test_set(0x00, 0, "CPH")
                yield from test_set(0x01, 0, "CPZ")
                yield from test_set(0x01, 1, "")
                yield from test_set(0x03, 0, "H")
                yield from test_set(0xff, 7, "N")
                yield from test_set(0xaa, 6, "F3")
                yield from test_res(0x00, 0, "CPH")
                yield from test_res(0x01, 0, "CPZ")
                yield from test_res(0x01, 1, "")
                yield from test_res(0x03, 0, "H")
                yield from test_res(0xff, 7, "N")
                yield from test_res(0xaa, 6, "F3")

            def random_add_sub_tests(test_cnt: int):
                import random as random
                print("Random add_sub tests")
                for i in range(test_cnt):
                    a = random.randrange(256)
                    b = random.randrange(256)
                    c = random.randrange(2)
                    yield from test_add(a,b,c)
                    yield from test_adc(a,b,c)
                    yield from test_sub(a,b,c)
                    yield from test_sbc(a,b,c)

            def directed_logic_tests():
                print("Directed logic tests")
                yield from test_or(0x0f, 0xf0, False)
                yield from test_or(0x00, 0xff, True)
                yield from test_or(0x00, 0x01, True)
                yield from test_or(0x01, 0x00, False)
                yield from test_and(0x0f, 0xf0, False)
                yield from test_and(0x20, 0xff, True)
                yield from test_and(0xf1, 0x01, True)
                yield from test_and(0x01, 0x0f, False)
                yield from test_xor(0x0f, 0xf0, False)
                yield from test_xor(0x20, 0xff, True)
                yield from test_xor(0xf1, 0x01, True)
                yield from test_xor(0x01, 0x0f, False)

            def directed_mov_inc_dec():
                print("Directed inc/dec/mov tests")
                yield from test_mov(0x01, "CHP")
                yield from test_mov(0x0f, "")
                yield from test_mov(0xf0, "NS")
                yield from test_inc(0x00, "CHP")
                yield from test_inc(0x01, "CHP")
                yield from test_inc(0x0f, "")
                yield from test_inc(0xf0, "NS")
                yield from test_inc(0xfe, "NS")
                yield from test_inc(0xff, "NS")
                yield from test_dec(0x00, "CHP")
                yield from test_dec(0x01, "CHP")
                yield from test_dec(0x0f, "")
                yield from test_dec(0xf0, "NS")
                yield from test_dec(0xfe, "NS")
                yield from test_dec(0xff, "NS")

            def directed_mov_inc_dec_16():
                print("Directed inc16/dec16/mov16 tests")
                yield from test_mov16(0x01, 0xe0, "CHP")
                yield from test_mov16(0x0f, 0xff, "")
                yield from test_mov16(0xf0, 0x00, "NS")
                yield from test_inc16(0x00, 0x00, "CHP")
                yield from test_inc16(0x01, 0x00, "CHP")
                yield from test_inc16(0x0f, 0xff, "")
                yield from test_inc16(0xf0, 0xa0, "NS")
                yield from test_inc16(0xfe, 0xff, "NS")
                yield from test_inc16(0xff, 0xff, "NS")
                yield from test_dec16(0x00, 0x00, "CHP")
                yield from test_dec16(0x01, 0x00, "CHP")
                yield from test_dec16(0x0f, 0xff, "")
                yield from test_dec16(0xf0, 0xa0, "NS")
                yield from test_dec16(0xfe, 0xff, "NS")
                yield from test_dec16(0xff, 0xff, "NS")

                yield from test_movz16(0x01, 0xe0, "CHP")
                yield from test_movz16(0x0f, 0xff, "")
                yield from test_movz16(0xf0, 0x00, "NS")
                yield from test_incz16(0x00, 0x00, "CHP")
                yield from test_incz16(0x01, 0x00, "CHP")
                yield from test_incz16(0x0f, 0xff, "")
                yield from test_incz16(0xf0, 0xa0, "NS")
                yield from test_incz16(0xfe, 0xff, "NS")
                yield from test_incz16(0xff, 0xff, "NS")
                yield from test_decz16(0x00, 0x00, "CHP")
                yield from test_decz16(0x01, 0x00, "CHP")
                yield from test_decz16(0x0f, 0xff, "")
                yield from test_decz16(0xf0, 0xa0, "NS")
                yield from test_decz16(0xfe, 0xff, "NS")
                yield from test_decz16(0xff, 0xff, "NS")

            import random as random
            random.seed(0,0)
            print("Simulation started")
            yield from directed_mist_tests()
            yield from directed_mov_inc_dec_16()
            yield from directed_mov_inc_dec()
            yield from directed_cp_tests()
            yield from directed_bit_tests()
            yield from directed_logic_tests()
            yield from directed_add_sub_tests()
            yield from directed_shift_tests()
            yield from random_add_sub_tests(20)
            print(f"Done")

    test.simulation(Z80Alu_tb, "z80_alu")

if __name__ == "__main__":
    test_sim()
    #test_verilog()
