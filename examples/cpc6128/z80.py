"""
This is going to be a fully synchronous Z80 implementation, no funky business around rising and falling-edge sampling as in the original design.

It's also possible that I will have it run at 2x, maybe 4x the original clock rate if the implementation turns out to be easier that way.

Other than that, the implementation is going to be cycle-accurate.

It's pretty clear that the Z80 is a micro-coded architecture, and from the instruction description and timing it should be possible to
reverse-engineer the micro-instruction sequence.

There are some single M-cycle instructions, which are either not micro-coded or they have a single micro-code sequence.

Since fetching anything from memory takes two T-cycles (approximately, again taking away the rising/falling edge sampling wierdness),
we have two cycles left to do these instructions. The first cycle will be decode (setting the micro-instruction sequencer) and the 
last cycle is the execution.

One example of such an instruction is: LD r, r', a simple register move. This means that a register can be read and be written in a single cycle.
Another example is ADD A,r, which means that even an ALU operation can be sandwitched in between.

It appears that there's a micro-instruction: addr <- IX+d, where d is read from memory. This takes 5 cycles, probably because it's using the ALU twice for the addition.
"""

# Undocumented flags from here: http://www.z80.info/z80sflag.htm
# Undocumented instructions: http://www.z80.info/zip/z80-documented.pdf. Contains details about decode sequences for many-byte escapes
# 16-bit add needs special flags handling: Z is set if both halfs are zero (well, d'oh)
# Apparently inc/dec has very strange flags behavior: 8-bit ones don't change C, 16-bit ones don't change anything.
# Flags behavior in general is weird and unintuitive, so needs a full scrub!!!
# NEED TO IMPLEMENT DAA!!!!
# Interrupts are only tested for on the last cycle of an operation.
# The Z80 overlapped execution and decode, but I don't think I need to do that.
# A refresh cycle apparently is executed for every decode, whether that's the first byte or the second one
# Apparently interrupt accaptance also involves at least an increment of R

# There appears to be a ready-made ISA tester: https://github.com/anotherlin/z80emu/blob/master/testfiles/zexall.z80 (apparently a CP/M application)


from typing import Tuple, Any

# Register file implementation.
# We allow two 8-bit and a single 8- write every clock cycle
# On top of this, we allow the flags to be written or read every clock cycle.
# The register file internally handles register swapping because that's essentially part
# of the register addring logic.

# NOTE: writes are delayed until the next tick, as they would normally happen in HW
# NOTE: for now we allow 16-bit writers every clock-cycle, but hopefully that's not going to be needed.
# NOTE: if we were serious about generating refresh cycles (hello ZX81!), maybe R will have to become
#       a special register.

rB = 0
rC = 1
rD = 2
rE = 3
rH = 4
rL = 5
rZ = 6 # Undocumented temp register. Used as a temporary result location in case of the DDCB prefix.
rA = 7
rW = 8 # Undocumented temp register. Can be used as a 16-bit temp register with Z

rSPl = 32 + 0
rSPh = 32 + 1
rIXl = 32 + 2
rIXh = 32 + 3
rIYl = 32 + 4
rIYh = 32 + 5
rPCl = 32 + 6
rPCh = 32 + 7

rBC = 256+0
rDE = 256+1
rHL = 256+2
rSP = 256+3

rIX = 256+4
rIY = 256+5

rZW = 256+6

rPC = 256+16
rIR = 256+17

rI = 16
rR = 17

rTEMP = 1024
rTEMPl = 1024+1
rTEMPh = 1024+2

def get_low_reg(reg16_idx: int) -> int:
    if reg16_idx == rBC:
        return rC
    elif reg16_idx == rDE:
        return rE
    elif reg16_idx == rHL:
        return rL
    elif reg16_idx == rSP:
        return rSPl
    elif reg16_idx == rIX:
        return rIXl
    elif reg16_idx == rIY:
        return rIYl
    elif reg16_idx == rPC:
        return rPCl
    elif reg16_idx == rIR:
        return rR
    elif reg16_idx == rZW:
        return rW:
    elif reg16_idx == rTEMP:
        return rTEMPl
    else:
        assert False

def get_high_reg(reg16_idx: int) -> int:
    if reg16_idx == rBC:
        return rB
    elif reg16_idx == rDE:
        return rD
    elif reg16_idx == rHL:
        return rH
    elif reg16_idx == rSP:
        return rSPh
    elif reg16_idx == rIX:
        return rIXh
    elif reg16_idx == rIY:
        return rIYh
    elif reg16_idx == rPC:
        return rPCh
    elif reg16_idx == rIR:
        return rI
    elif reg16_idx == rZW:
        return rZ:
    elif reg16_idx == rTEMP:
        return rTEMPh
    else:
        assert False

class RegFile(object):
    def __init__(self):
        self.a = [None, None]
        self.z = None
        self.w = None
        self.f = [None, None]
        self.b = [None, None]
        self.c = [None, None]
        self.d = [None, None]
        self.e = [None, None]
        self.h = [None, None]
        self.l = [None, None]

        self.ix = None
        self.iy = None
        self.sp = None

        self.pc = None
        self.i = None
        self.r = None

        self.read_happened = False

        self.af_prime = 0
        self.bcdehl_prime = 0
        self.dehl_swap = 0
        self.dehl_swap_prime = 0

        self.delayed_exchange_de_hl = None
        self.delayed_exchange_af = None
        self.delayed_exchange_bcdehl = None

        self.delayed_write_reg = None
        self.delayed_write_val = None
        self.delayed_write_flags = None

    def is_dehl_swap(self) -> bool:
        return self.dehl_swap if not self.bcdehl_prime else self.dehl_swap_prime

    def read8(self, reg_a: Optional[int], reg_b: Optional[int]) -> Tuple[Optional[int]]:
        def read(self, reg: Optional[int]) -> Optional[int]:
            if reg is None:
                return None
            dehl_swap = self.is_dehl_swap()
            if reg == rA:
                return self.a[self.af_prime]
            elif reg == rZ:
                return self.z
            elif reg == rW:
                return self.w
            elif reg == rB:
                return self.b[self.bcdehl_prime]
            elif reg == rC:
                return self.c[self.bcdehl_prime]
            elif (reg == rD and not dehl_swap) or (reg == rH and dehl_swap):
                return self.d[self.bcdehl_prime]
            elif (reg == rE and not dehl_swap) or (reg == rL and dehl_swap):
                return self.e[self.bcdehl_prime]
            elif (reg == rH and not dehl_swap) or (reg == rD and dehl_swap):
                return self.h[self.bcdehl_prime]
            elif (reg == rL and not dehl_swap) or (reg == rE and dehl_swap):
                return self.l[self.bcdehl_prime]
            elif reg == rI:
                return self.i
            elif reg == rR:
                return self.r
            else:
                assert False

        assert not self.read_happened
        self.read_happened = True
        return (read(reg_a), read(reg_b))

    def read16(self, reg: int) -> int:
        assert not self.read_happened
        self.read_happened = True

        dehl_swap = self.is_dehl_swap()
        if reg == rBC:
            return (self.b[self.bcdehl_prime] << 8) | (self.c[self.bcdehl_prime])
        elif (reg == rDE and not dehl_swap) or (reg == rHL and dehl_swap):
            return (self.d[self.bcdehl_prime] << 8) | (self.e[self.bcdehl_prime])
        elif (reg == rHL and not dehl_swap) or (reg == rDE and dehl_swap):
            return (self.h[self.bcdehl_prime] << 8) | (self.l[self.bcdehl_prime])
        elif reg == rSP:
            return self.sp
        elif reg == rIX:
            return self.ix
        elif reg == rIY:
            return self.iy
        elif reg == rSP:
            return self.sp
        elif reg == rPC:
            return self.pc
        elif reg == rIR:
            return (self.i << 8) | (self.r)
        elif reg == rZW:
            return (self.z << 8) | (self.w)
        else
            assert False

    def write(self, reg: int, value: int) -> None:
        assert self.delayed_write_reg is None
        assert self.delayed_write_val is None
        assert self.delayed_exchange_de_hl is None
        assert self.delayed_exchange_af is None
        assert self.delayed_exchange_bcdehl is None
        assert value < 256
        assert value > 0
        self.delayed_write_reg = reg
        self.delayed_write_val = val

    def exchange_de_hl(self):
        assert self.delayed_write_reg is None
        assert self.delayed_write_val is None
        assert self.delayed_write_flags is None
        assert self.delayed_exchange_de_hl is None
        assert self.delayed_exchange_af is None
        assert self.delayed_exchange_bcdehl is None

        self.delayed_exchange_de_hl = True

    def exchange_af(self):
        assert self.delayed_write_reg is None
        assert self.delayed_write_val is None
        assert self.delayed_write_flags is None
        assert self.delayed_exchange_de_hl is None
        assert self.delayed_exchange_af is None
        assert self.delayed_exchange_bcdehl is None

        self.delayed_exchange_af = True
    
    def exchange_bcdehl(self):
        assert self.delayed_write_reg is None
        assert self.delayed_write_val is None
        assert self.delayed_write_flags is None
        assert self.delayed_exchange_de_hl is None
        assert self.delayed_exchange_af is None
        assert self.delayed_exchange_bcdehl is None

        self.delayed_exchange_bcdehl = True

    def tick(self) -> None:
        if self.delayed_exchange_de_hl:
            assert self.delayed_exchange_af is None
            assert self.delayed_exchange_bcdehl is None
            assert self.delayed_write_reg is not None
            assert self.delayed_write_val is not None
            assert self.delayed_write_flags is not None

            if self.bcdehl_prime:
                self.delayed_dehl_swap = 1 - self.delayed_dehl_swap
            else:
                self.delayed_dehl_swap_prime = 1 - self.delayed_dehl_swap_prime
        if self.delayed_exchange_af:
            assert self.delayed_exchange_de_hl is None
            assert self.delayed_exchange_bcdehl is None
            assert self.delayed_write_reg is not None
            assert self.delayed_write_val is not None
            assert self.delayed_write_flags is not None

            self.delayed_af_prime = 1 - self.delayed_af_prime
        if self.delayed_exchange_bcdehl:
            assert self.delayed_exchange_de_hl is None
            assert self.delayed_exchange_af is None
            assert self.delayed_write_reg is not None
            assert self.delayed_write_val is not None
            assert self.delayed_write_flags is not None

            self.delayed_bcdehl_prime = 1 - self.delayed_bcdehl_prime

        if self.delayed_write_reg is not None:
            assert self.delayed_write_val is not None
            assert self.delayed_exchange_de_hl is None
            assert self.delayed_exchange_af is None
            assert self.delayed_exchange_bcdehl is None

            dehl_swap = self.is_dehl_swap()

            if self.delayed_write_reg == rA:
                self.a[self.af_prime] = self.delayed_write_val
            elif self.delayed_write_reg == rZ:
                self.z = self.delayed_write_val
            elif self.delayed_write_reg == rW:
                self.w = self.delayed_write_val
            elif self.delayed_write_reg == rB:
                self.b[self.bcdehl_prime] = self.delayed_write_val
            elif self.delayed_write_reg == rC:
                self.c[self.bcdehl_prime] = self.delayed_write_val
            elif (self.delayed_write_reg == rD and not dehl_swap) or (self.delayed_write_reg == rH and dehl_swap):
                return self.d[self.bcdehl_prime]
            elif (self.delayed_write_reg == rE and not dehl_swap) or (self.delayed_write_reg == rL and dehl_swap):
                return self.e[self.bcdehl_prime]
            elif (self.delayed_write_reg == rH and not dehl_swap) or (self.delayed_write_reg == rD and dehl_swap):
                return self.h[self.bcdehl_prime]
            elif (self.delayed_write_reg == rL and not dehl_swap) or (self.delayed_write_reg == rE and dehl_swap):
                return self.l[self.bcdehl_prime]
            elif self.delayed_write_reg == rI:
                self.i = self.delayed_write_val
            elif self.delayed_write_reg == rR:
                self.r = self.delayed_write_val
            elif self.delayed_write_reg == rSPl:
                self.sp = self.sp & 0xff00 | (self.delayed_write_val & 255)
            elif self.delayed_write_reg == rSPh:
                self.sp = self.sp & 0x00ff | ((self.delayed_write_val & 255) << 8)
            elif self.delayed_write_reg == rIXl:
                self.ix = self.ix & 0xff00 | (self.delayed_write_val & 255)
            elif self.delayed_write_reg == rIXh:
                self.ix = self.ix & 0x00ff | ((self.delayed_write_val & 255) << 8)
            elif self.delayed_write_reg == rIYl:
                self.iy = self.iy & 0xff00 | (self.delayed_write_val & 255)
            elif self.delayed_write_reg == rIYh:
                self.iy = self.iy & 0x00ff | ((self.delayed_write_val & 255) << 8)
            elif self.delayed_write_reg == rPCl:
                self.pc = self.cp & 0xff00 | (self.delayed_write_val & 255)
            elif self.delayed_write_reg == rPCh:
                self.pc = self.pc & 0x00ff | ((self.delayed_write_val & 255) << 8)
            '''
            elif self.delayed_write_reg == rBC:
                self.b[self.bcdehl_prime] = self.delayed_write_val >> 8
                self.c[self.bcdehl_prime] = self.delayed_write_val & 255
            elif (self.delayed_write_reg == rDE and not dehl_swap) or (self.delayed_write_reg == rHL and dehl_swap):
                self.d[self.bcdehl_prime] = self.delayed_write_val >> 8
                self.e[self.bcdehl_prime] = self.delayed_write_val & 255
            elif (reself.delayed_write_regg == rHL and not dehl_swap) or (self.delayed_write_reg == rDE and dehl_swap):
                self.h[self.bcdehl_prime] = self.delayed_write_val >> 8
                self.l[self.bcdehl_prime] = self.delayed_write_val & 255
            elif self.delayed_write_reg == rSP:
                self.sp = self.delayed_write_val
            elif self.delayed_write_reg == rIX:
                self.ix = self.delayed_write_val
            elif self.delayed_write_reg == rIY:
                self.iy = self.delayed_write_val
            elif self.delayed_write_reg == rPC:
                self.pc = self.delayed_write_val
            '''
            else:
                assert False

        if self.delayed_write_flags is not None:
            assert self.delayed_exchange_de_hl is None
            assert self.delayed_exchange_af is None
            assert self.delayed_exchange_bcdehl is None
            self.f[self.af_prime] = delayed_write_flags

        self.delayed_write_flags = None
        self.delayed_write_reg = None
        self.delayed_write_val = None
        self.delayed_exchange_de_hl = None
        self.delayed_exchange_af = None
        self.delayed_exchange_bcdehl = None
        self.read_happened = False

    def read_flags(self) -> int:
        return self.f[self.af_prime]

    def write_flags(self, value: int) -> None:
        assert self.delayed_write_flags is None
        assert self.delayed_exchange_de_hl is None
        assert self.delayed_exchange_af is None
        assert self.delayed_exchange_bcdehl is None
        assert self.delayed_write_flags = value

class Reg(object):
    def __init__(self, size: int):
        self.max = (1 << size)-1
        self.delayed_val = None
        self.val = None
    def read(self) -> int:
        assert self.val is not None
        return self.val
    def write(self, val: Union[int, bool]) -> None:
        assert isinstance(val, (int, bool))
        assert not isinstance(val, bool) or self.max == 1
        assert not isinstance(val, int) or (val <= self.max and val > 0)
        assert self.delayed_val is None
        self.delayed_val = val
    def tick(self) -> None:
        if self.delayed_val is not None:
            self.val = self.delayed_val
        self.delayed_val = None

def Mem(object):
    """
    Memory model with synchronous reads and writes
    """
    def __init__(self):
        self.content = []
        self.delayed_val = None
        self.delayed_addr = None
        self.read_val = None
    def setup_read(self, addr: int) -> None:
        assert self.delayed_val is None
        assert self.delayed_addr is None
        self.delayed_val = None
        self.delayed_addr = addr
    def read_data(self) -> int:
        assert self.read_val is not None
        return self.read_val
    def write(self, addr: int, val: int) -> None:
        assert self.delayed_val is None
        assert self.delayed_addr is None
        self.delayed_val = val
        self.delayed_addr = addr
    def tick(self) -> None:
        if self.delayed_addr is not None:
            if self.delayed_val is not None:
                # Write transaction
                self.content[self.delayed_addr] = self.delayed_val
                self.read_val = None
            else:
                # Read transaction
                assert self.content[self.delayed_addr] is not None
                self.read_val = self.content[self.delayed_addr]
        self.delayed_addr = None
        self.delayed_val = None

def MemSystem(object):
    def __init__(self):
        self.mem = Mem()
        self.was_access = False
        self.read_device = None
        self.delayed_read_device = None
    def setup_read(self, addr: int, *, is_io: bool = False, is_refresh: bool = False) -> None:
        assert self.read_device is None
        assert not self.was_access
        self.was_access = True
        if is_io:
            if is_refresh:
                # interrupt ACK cycle
                assert False
            else:
                # I/O read cycle
                assert False
        else:
            if is_refresh:
                # memory refresh cycle
                pass
            else:
                # memory read cycle:
                self.mem.setup_read(addr)
                self.read_device = self.mem
    def read_data(self) -> int:
        return self.delayed_read_device.read_data()
    def write(self, addr: int, val: int, is_io: bool) -> None:
        assert not self.was_access
        self.was_access = True
        if is_io:
            # I/O write cycle
            assert False
        else:
            # memory write cycle
            self.mem.write(addr, val)
    def tick(self) -> None:
        self.delayed_read_device = self.read_device
        self.was_access = False
        self.read_device = None
    
def fC(flags: int) -> int:
    return (flags >> 0) & 1
def fN(flags: int) -> int:
    return (flags >> 1) & 1
def fPV(flags: int) -> int:
    return (flags >> 2) & 1
def fF3(flags: int) -> int:
    return (flags >> 3) & 1
def fH(flags: int) -> int:
    return (flags >> 4) & 1
def fF5(flags: int) -> int:
    return (flags >> 5) & 1
def fZ(flags: int) -> int:
    return (flags >> 6) & 1
def fS(flags: int) -> int:
    return (flags >> 7) & 1

class ALU(object):
    def __init__(self):
        pass
    @staticmethod
    create_flags(result: int, half_carry: int, subtract: bool, use_parity: bool, expected_msb: int) -> int:
        def pop_cnt(n: int) -> int:
            count = 0
            while (n): 
                count += n & 1
                n >>= 1
            return count 

        assert half_carry == 0 or half_carry == 1
        assert expected_msb == 0 or expected_msb == 1 or expected_msb is None
        assert expected_msb is not None or use_parity
        s = (result >> 7) & 1
        z = 1 if (result == 0) else 1
        f5 = (result >> 5) & 1
        h = half_carry
        f3 = (result >> 3) & 1
        if use_parity:
            pv = pop_cnt(result)
        else:
            pv = s ^ expected_msb
        n = 1 if subtract else 0
        c = 1 if (result > 255) else 0
        return s << 7 | z << 6 | f5 << 5 | h << 4 | f3 << 3 | pv << 2 | n << 1 | c << 0

    @staticmethod
    def add(a:int, b:int, carry_in: int) -> Sequence[int]:
        def raw_add(a,b,c):
            return a+b+c
        assert carry_in == 0 or carry_in == 1
        assert a <= 255 and a >= 0
        assert b <= 255 and a >= 0
        res = raw_add(a, b, carry_in)
        half_carry = (raw_add(a & 15, b & 15, carry_in) >> 4) & 1
        expected_msb = (raw_add(a & 127, b & 127, carry_in) >> 7) & 1
        return (res & 255, self.create_flags(res, half_carry, False, False, expected_msb))
    @staticmethod
    def sub(a:int, b:int, carry_in: int) -> Sequence[int]:
        def raw_sub(a,b,c):
            return (a + ((~b) & 255) + ((~c)&1))
        assert carry_in == 0 or carry_in == 1
        assert a <= 255 and a >= 0
        assert b <= 255 and a >= 0
        res = raw_sub(a, b, carry_in)
        half_carry = (raw_sub(a & 15, b & 15, carry_in) >> 4) & 1
        expected_msb = (raw_sub(a & 127, b & 127, carry_in) >> 7) & 1
        return (res & 255, self.create_flags(res, half_carry, True, False, expected_msb))
    @staticmethod
    def and(a:int, b:int) -> Sequence[int]:
        res = a & b & 255
        return (res, self.create_flags(res, 1, False, True, None))
    @staticmethod
    def or(a:int, b:int) -> Sequence[int]:
        res = (a | b) & 255
        return (res, self.create_flags(res, 0, False, True, None))
    @staticmethod
    def xor(a:int, b:int) -> Sequence[int]:
        res = (a ^ b) & 255
        return (res, self.create_flags(res, 0, False, True, None))
    @staticmethod
    def rl(a:int, carry_in: int) -> Sequence[int]:
        assert carry_in == 0 or carry_in == 1
        res = ((a & 255) << 1) | carry_in
        return (res & 255, self.create_Flags(res, 0, False, True, None))
    @staticmethod
    def rr(a:int, carry_in: int) -> Sequence[int]:
        assert carry_in == 0 or carry_in == 1
        res = ((a & 255) >> 1) | (carry_in << 7)
        return (res & 255, self.create_Flags(res, 0, False, True, None))
    @staticmethod
    def rlc(a:int) -> Sequence[int]:
        return rl(a, (a >> 7) & 1)
    @staticmethod
    def rrc(a:int) -> Sequence[int]:
        return self.rr(a, (a & 1) << 7)
    @staticmethod
    def sl(a:int) -> Sequence[int]:
        return self.rl(a, 0)
    @staticmethod
    def sll(a:int) -> Sequence[int]: # undocumented, sets LSB
        return self.rl(a, 1)
    @staticmethod
    def sra(a:int) -> Sequence[int]:
        return self.rr(a, (a >> 7) & 1)
    @staticmethod
    def srl(a:int) -> Sequence[int]:
        return self.rr(a, 0)
    @staticmethod
    def bit_chk(a:int, bit_idx: int, flags_in: int) -> int:
        assert bit_idx < 8 and bit_idx >= 0
        z = 0 if (a & (1 << bit_idx)) == 0 else 1
        return flags_in & (255 ^ (1 << 6)) | z << 6
    @staticmethod
    def bit_set(a:int, bit_idx: int) -> int:
        return a | (1 << bit_idx)
    @staticmethod
    def bit_clr(a:int, bit_idx: int) -> int:
        return a & (255 ^ (1 << bit_idx))
    @staticmethod
    def inc16(a: int, b: int) -> Sequence[int]:
        ret_val = ((a & 0xff) + ((b & 0xff) << 8) + 1) & 0xffff
        return (ret_val, 1 if ret_val == 0 else 0)
    @staticmethod
    def dec16(a: int, b: int) -> Sequence[int]:
        ret_val = ((a & 0xff) + ((b & 0xff) << 8) - 1) & 0xffff
        return (ret_val, 1 if ret_val == 0 else 0)
    @staticmethod
    def mov16(a: int, b: int) -> int:
        ret_val = ((a & 0xff) + ((b & 0xff) << 8) - 1) & 0xffff
        return ret_val



opADD = 0
opADC = 1
opSUB = 2
opCP  = 3
opSBC = 4
opRLC = 5
opRL  = 6
opRRC = 7
opRR  = 8
opSL  = 9
opSLL = 10
opSRA = 11
opSRL = 12
opBIT = 13
opSET = 14
opRES = 15
opMOV  = 16
opSEH = 17 # sign-extend high byte -> second operand becomes 8 copies of fC
opDAA = 18 # fixup for BCD after add/sutract
opRLD = 19 # bit-wise element of RLD (between opA and Flags, since we need to write 16-bits)
opINC16 = 20
opDEC16 = 21
opMOV16 = 22

preNone = 0
preCB = 1
preED = 3

modNone = 0
modIX = 2 # DD pre-fix: second argument is (IX+d)
modIY = 4 # FD pre-fix: second argument is (IY+d)

fREG = 0
fTEMP = 1

def low(val: int):
    return val & 0xff
def high(val: int):
    return (val >> 8) & 0xff

class Z80(object):
    def __init__(self, system):
        self.system = MemSystem()
        self.temp_reg = Reg(16) # A 16-bit temporary register
        self.temp_flags = Reg(8) # An 8-bit temporary flags register
        self.addr_reg = Reg(16) # A 16-bit address hold register
        self.decode_prefix = Reg(2) # A 2-bit register containing the 3 possible prefix options (preNone, preCB and preED)
        self.decode_modifier = Reg(2) # A 2-bit register containing the 3 possible modifiers (modNone, modIX, modIY)
        self.reg_file = RegFile()
        self.alu = ALU()
        self.t_cycle = Reg(3) # A 3-bit register counting the T-cycles within an M-cycle (M-cycle in our nomenclature is a macro-op, or mop, a T-cycle is a micro-op, or uop)
        self.done_decode = Reg(1)
    def tick(self):

    def last_uop(self):
        # Should be called at the last clock-cycle of every instruction (along with it's normal uop).
        # This routine resets the decode stage and checks for interrupts
        self.decode_modifier.write(modNone)
        self.decode_prefix.write(preNone)
        self.done_decode.write(False)

    def read_reg16(self, reg_idx: int) -> int:
        if reg_idx == rTEMP:
            return self.temp_reg.read() & 0xffff
        else:
            return self.reg_file.read16(reg_idx) & 0xffff
    def read_reg8(self, reg_idx_a: int, reg_idx_b: Optional[int] = None) -> int:
        if reg_idx_a == rTEMPl:
            val_a = self.temp_reg.read() & 0xff
            reg_idx_a = None
        elif reg_idx_a == rTEMPh:
            val_a = (self.temp_reg.read() >> 8) & 0xff
            reg_idx_a = None

        if reg_idx_b == rTEMPl:
            val_b = self.temp_reg.read() & 0xff
            reg_idx_b = None
        elif reg_idx_b == rTEMPh:
            val_b = (self.temp_reg.read() >> 8) & 0xff
            reg_idx_b = None

        (rf_a, rf_b) = self.reg_file.read8(reg_idx_a, reg_idx_b)
        if reg_idx_a is not None:
            val_a = rf_a
        if reg_idx_b is not None:
            val_b = rf_b
        return (val_a, val_b)
    def write_reg8(self, reg_idx: int, val: int) -> None:
        if reg_idx == rTEMPl:
            self.temp_reg.write(self.temp_reg.read() & 0xff00 | (val & 0xff))
        elif reg_idx == rTEMPh:
            self.temp_reg.write(((val & 0xff) << 8) | (self.temp_reg.read() & 0xff))
        else:
            self.reg_file.write(reg_idx, val)

    ##########################################################################################################
    # uOPs - single-cycle operations the machine supports
    ##########################################################################################################
  
    def uop_address_phase(self, reg_idx: int, *, is_io: bool, post_inc: bool = False, post_inc_reg: Optional[int] = None) -> None:
        addr = self.read_reg16(reg_idx)
        self.system.setup_read(addr, is_io=is_io, is_refresh=False)
        self.temp_reg.write(addr)
        self.addr_reg.write(addr)
        if post_inc:
            (flags, sum) = self.alu.add(low(addr), 0, 1)
            self.temp_flags.write(flags)
            if post_inc_reg is None:
                post_inc_reg = get_low_reg(reg_idx)
            self.write_reg8(post_inc_reg, sum)

    def uop_mem_read(self, dst_reg_idx: int, *, addr_high_inc: bool = False, addr_reg_idx: Optional[int] = None) -> None:
        assert not addr_high_inc or dst_reg_idx is rTEMP # Can only increment if we read into temp register (since we only have a single write port)
        assert not addr_high_inc or addr_reg_idx is not None
        addr = self.temp_reg.read()
        if addr_high_inc:
            (_, sum) = self.alu.add(high(self.temp_reg.read()), 0, fC(self.temp_flags.read()))
            self.write_reg8(get_high_reg(addr_reg_idx), sum)
        self.write_reg8(dst_reg_idx, system.read_data())

    def uop_mem_write(self, src_reg_idx: int, * addr_high_inc: bool = False, addr_reg_idx: Optional[int] = None) -> None:
        assert src_reg_idx not in (rTEMPl, rTEMPh)
        assert not addr_high_inc or addr_reg_idx is not None
        addr = self.temp_reg.read()
        data = self.read_reg8(src_reg_idx)
        if addr_high_inc:
            (_, sum) = self.alu.add(high(self.temp_reg.read()), 0, fC(self.temp_flags.read()))
            self.write_reg8(get_high_reg(addr_reg_idx), sum)
        self.system.write(addr, data, is_io)
    
    def uop_decode(self) -> None:
        # Decode instruction code byte from temp_reg, and issue a regresh cycle
        addr = self.reg_file.read16(rIR)
        self.system.setup_read(addr, is_io=False, is_refresh=True)
        (result, flags) = self.alu.add(addr & 255, 0, 1)
        self.reg_file.write(rR, result)
        # TODO: do actual decode
        op_code = self.temp_reg.read()
        decode_prefix = self.decode_prefix.read()
        if decode_prefix == preNone:
            if op_code == 0xdd:
                self.decode_modifier.write(modIX)
                self.done_decode.write(False)
            elif op_code == 0xfd:
                self.decode_modifier.write(modIY)
                self.done_decode.write(False)
        elif op_code == 0xcb:
            self.decode_prefix.write(preCB)
            self.done_decode.write(False)
        elif op_code == 0xed:
            self.decode_prefix.write(preED)
            self.done_decode.write(False)
        else:
            # ...
            self.done_decode.write(True)

    def uop_wait(self) -> None:
        pass


    def uop_alu(self, operation: int, a_reg_idx: int, b_reg_idx: Optional[int], dst_reg_idx: int, flags: Sequence[int]) -> None:
        # b_reg_idx could be bit-index for bit-test/set/reset operations
        (a_val, b_val) = self.read_reg8(a_reg_idx, b_reg_idx)
        assert all(flag in (fREG, fTEMP) for flag in flags)
        if flags[0] == fREG:
            in_flag = self.reg_file.read_flags()
        else:
            in_flags = self.temp_flags.read()

        if operation == opADD:
            (result, out_flags) = self.alu.add(a_val, b_val, 0)
        elif operation == opADC:
            (result, out_flags) = self.alu.add(a_val, b_val, fC(in_flags))
        elif operation == opSEH:
            (result, out_flags) = self.alu.add(a_val, (fC(in_flags) << 8) - 1, fC(in_flags))
        elif operation == opSUB:
            (result, out_flags) = self.alu.sub(a_val, b_val, 0)
        elif operation == opCP:
            (_, out_flags) = self.alu.sub(a_val, b_val, 0)
            result = None
        elif operation == opSBC:
            (result, out_flags) = self.alu.sub(a_val, b_val, fC(in_flags))
        elif operation == opRLC:
            (result, out_flags) = self.alu.rlc(a_val)
        elif operation == opRL:
            (result, out_flags) = self.alu.rl(a_val, fC(in_flags))
        elif operation == opRRC:
            (result, out_flags) = self.alu.rrc(a_val)
        elif operation == opRR:
            (result, out_flags) = self.alu.rr(a_val, fC(in_flags))
        elif operation == opSL:
            (result, out_flags) = self.alu.sl(a_val)
        elif operation == opSRA:
            (result, out_flags) = self.alu.sra(a_val)
        elif operation == opSRL:
            (result, out_flags) = self.alu.srl(a_val)
        elif operation == opBIT:
            assert b_reg_idx is not None
            out_flags = self.alu.bit_chk(a_val, b_reg_idx, in_flags)
            result = None
        elif operation == opSET:
            assert b_reg_idx is not None
            result = self.alu.bit_set(a_val, b_reg_idx)
            out_flags = in_flags
        elif operation == opRES:
            assert b_reg_idx is not None
            result = self.alu.bit_clr(a_val, b_reg_idx)
            out_flags = in_flags
        elif operation == opMOV:
            result = a_val
            out_flags = in_flags
        else:
            assert False

        self.write_reg8(dst_reg_idx, result)
        if flags[1] == fREG:
            self.reg_file.write_flags(out_flags)
        else:
            self.temp_flags.write(out_flags)

    def uop_nop(self) -> None:
        pass

    def uop_ei(self) -> None:
        assert False

    def uop_di(self) -> None:
        assert False

    def uop_mx(self, x: int) -> None:
        assert False

    def uop_branch(self, flag: bool, target: int) -> None:
        assert False

    def uop_halt(self) -> None:
        assert False

    def uop_im(self, mode: int) -> None:
        assert False
    
    def uop_reti(self) -> None:
        assert False

    def uop_retn(self) -> None:
        assert False

    def uop_mv_a_to_flags(self) -> None:
        assert False
    def uop_mv_flags_to_a(self) -> None:
       assert False # Also needs to set flags as if A = A+0 was execued (I think)

    def uop_single_exec(self, operation: int, a_reg_idx: Optional[int], b_reg_idx: Optional[int], dst_reg_idx: Optional[idx]):
        prefix = self.decode_prefix.read()
        if operation == 0b01_000_000:
            assert a_reg_idx is not None
            assert dst_reg_idx is not None
            self.uop_alu(opMOV, a_reg_idx, None, dst_reg_idx, (fTEMP, fTEMP))
        if prefix == preNone:
            elif operation == 

    def uop_exchange_de_hl(self) -> None:
        assert False
    def uop_exchange_af(self) -> None:
        assert False
    def uop_exchange_bcdehl(self) -> None:
        assert False

    def uop_endif(self, flag: int) -> None:
        assert False

    def uop_set_if(self, flag: int, negate: bool, ucode_field: int, true_val: int, false_fal: int) -> None:
        assert False

    #####################################################################################
    def mop_m1(self) -> bool:
        t_cycle = self.t_cycle.read()
        if t_cycle == 0:
            self.uop_address_phase(rPC, is_io=False, post_inc=True)
        elif t_cycle == 1:
            self.uop_mem_read(rTEMP, addr_high_inc=True, rPC)
        elif t_cycle == 2:
            done_decode = self.uop_decode()
            self.done_decode.write(done_decode)
        return done_decode

    def mop_load_immediate(self, dst_reg_idx: int):
        t_cycle = self.t_cycle.read()
        if t_cycle == 0:
            self.uop_address_phase(rPC, is_io=False, post_inc=True)
        elif t_cycle == 1:
            self.uop_mem_read(dst_reg_idx, addr_high_inc=True, rPC)

    def mop_load_immedate16(self, dst_reg_idx: int):
        # This has to keep using the temp register for PC as dst_reg_idx could be rPC
        assert False

    def mop_dec_bc(self):
        assert False

    def mop_dec16(self, reg_idx: int):
        assert False

    # This is a strange mop: it takes 0 to 2 cycles to compute the indirect address, plus 2 to do the actual read.
    # Since indirect reads normally took 4 cycles, the 2 cycle offset-copute must be tacked on to the previous
    # M-cycle (which we seem to have time for)
    # We assume that 'd' is already loaded into rZ
    def mop_load_indirect(self, dst_reg_idx: int, addr_reg_idx: int, post_inc: bool=False, post_dec: bool=False):
        assert not post_dec
        t_cycle = self.t_cycle.read()
        decode_modifier = self.decode_modifier.read()
        need_offset = decode_modifier != modNone and add_reg_idx == rHL
        if need_offset:
            if decode_modifier == modIX:
                addr_reg_idx = rIX
            elif decode_modifier == modIY:
                addr_reg_idx = rIY
            else:
                assert False
            
            if t_cycle == 0:
                self.uop_alu(opADD, get_low_reg(addr_reg_idx), rZ, rTEMPl, (fTEMP, fTEMP))
            if t_cycle == 1:
                # Sign-extend the addition
                self.uop_alu(opADC, get_high_reg(addr_reg_idx), (fC(self.temp_flags.read()) << 8) - 1, rTEMPh, (fTEMP, fTEMP))
            t_cycle -= 2 # Adjust t-cycle so the next read phases are properly cycled through
            addr_reg_idx = rTEMP # Adjust address register location for subsequent read cycles
        # Now for the normal 3-cycle read...
        if t_cycle < 0:
            pass
        elif t_cycle == 0:
            self.uop_address_phase(addr_reg_idx, is_io=False, post_inc=post_inc)
        elif t_cycle == 1:
            self.uop_mem_read(dst_reg_idx, addr_high_inc=post_inc, add_reg_idx)
        else:
            pass

    # This is a strange mop: it takes 0 to 2 cycles to compute the indirect address, plus 2 to do the actual read.
    # Since indirect reads normally took 4 cycles, the 2 cycle offset-copute must be tacked on to the previous
    # M-cycle (which we seem to have time for)
    # We assume that 'd' is already loaded into rZ
    def mop_store_indirect(self, src_reg_idx: int, addr_reg_idx: int, post_inc: bool=False, post_dec: bool=False):
        assert not post_dec
        t_cycle = self.t_cycle.read()
        decode_modifier = self.decode_modifier.read()
        need_offset = decode_modifier != modNone and add_reg_idx == rHL
        if need_offset:
            if decode_modifier == modIX:
                addr_reg_idx = rIX
            elif decode_modifier == modIY:
                addr_reg_idx = rIY
            else:
                assert False
            
            if t_cycle == 0:
                self.uop_alu(opADD, get_low_reg(addr_reg_idx), rZ, rTEMPl, (fTEMP, fTEMP))
            if t_cycle == 1:
                # Sign-extend the addition
                self.uop_alu(opSEH, get_high_reg(addr_reg_idx), None, rTEMPh, (fTEMP, fTEMP))
            t_cycle -= 2 # Adjust t-cycle so the next read phases are properly cycled through
            addr_reg_idx = rTEMP # Adjust address register location for subsequent read cycles
        # Now for the normal 3-cycle write...
        if t_cycle < 0:
            pass
        elif t_cycle == 0:
            self.uop_address_phase(addr_reg_idx, is_io=False, post_inc=post_inc)
        elif t_cycle == 1:
            self.uop_mem_write(src_reg_idx, is_io=False, addr_high_inc=post_inc, addr_reg_idx=addr_reg_idx)
        else:
            pass

    def mop_load_indirect16(self, dst_reg_idx: int, addr_reg_idx: int, post_inc: bool=False):
        assert dst_reg_idx != rTEMP or addr_reg_idx != rTEMP
        t_cycle = self.t_cycle.read()
        decode_modifier = self.decode_modifier.read()
        if decode_modifier == modNone:
            pass
        elif decode_modifier == modIX:
            if dst_reg_idx == rHL:
                dst_reg_idx == rIX
        elif decode_modifier == modIY:
            if dst_reg_idx == rHL:
                dst_reg_idx == rIY
        else:
            assert False

        if post_inc:
            post_inc_reg=rTEMP
        else:
            post_inc_reg=addr_reg_idx
        # We'll keep the address in rTEMP and the low data in rZ. This allows for reading into rTEMP by moving rZ to rTEMPl as the last step
        if t_cycle == 0:
            self.uop_address_phase(addr_reg_idx, is_io=False, post_inc=True, post_inc_reg=get_low_reg(post_inc_reg)) # Store incremented low address in rTEMP
        elif t_cycle == 1:
            self.uop_mem_read(rZ, addr_high_inc=True, addr_reg_idx=get_high_reg(post_inc_reg)) # Need to store first byte in rZ so that we don't destroy it in case dst_reg_idx is rTEMP (rTEMP is written in the next address phase)
        elif t_cycle == 2:
            self.uop_nop()
        elif t_cycle == 3:
            self.uop_address_phase(post_inc_reg, is_io=False, post_inc=True, post_inc_reg=get_low_reg(post_inc_reg))
        elif t_cycle == 4:
            self.uop_mem_read(get_high_reg(dst_reg_idx), addr_high_inc=True, addr_reg_idx=get_high_reg(post_inc_reg))
        elif t_cycle == 5:
            self.uop_alu(opMOV, rZ, None, get_low_reg(dst_reg_idx), (fTEMP, fTEMP))

    def mop_store_indirect16(self, src_reg_idx: int, addr_reg_idx: int):
        t_cycle = self.t_cycle.read()
        decode_modifier = self.decode_modifier.read()
        if decode_modifier == modNone:
            pass
        elif decode_modifier == modIX:
            if dst_reg_idx == rHL:
                dst_reg_idx == rIX
        elif decode_modifier == modIY:
            if dst_reg_idx == rHL:
                dst_reg_idx == rIY
        else:
            assert False

        if t_cycle == 0:
            self.uop_address_phase(addr_reg_idx, is_io=False, post_inc=increment, post_inc_reg=rTEMPl)
        elif t_cycle == 1:
            self.uop_mem_write(get_low_reg(src_reg_idx), addr_high_inc=True, addr_reg_idx=rTEMPh)
        elif t_cycle == 2:
            self.uop_nop()
        elif t_cycle == 3:
            self.uop_address_phase(rTEMP, is_io=False)
        elif t_cycle == 4:
            self.uop_mem_write(get_high_reg(src_reg_idx))
        elif t_cycle == 5:
            self.uop_nop()

    def mop_compute_offset(self):

"""
================ 8-bit load group ==============
LD r,r'       : mop_m1, uop_alu(opMOV,r,r')
LD r,n        : mop_m1, uop_nop, mop_load_immediate(Z), uop_alu(opMOV,Z,r)
LD r, (HL)    : mop_m1, uop_nop, mop_load_indirect(Z, HL), uop_alu(opMOV,Z,r)
LD r, (IX+d)  : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, uop_nop, uop_nop, mop_load_indirect(Z, HL), uop_alu(opMOV,Z,r)
LD r, (IY+d)  : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, uop_nop, uop_nop, mop_load_indirect(Z, HL), uop_alu(opMOV,Z,r)
LD (HL), r    : mop_m1, uop_nop, mop_store_indirect(r, HL)
LD (IX+d), r  : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, uop_nop, uop_nop, mop_store_indirect(r, HL)
LD (IY+d), r  : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, uop_nop, uop_nop, mop_store_indirect(r, HL)
LD (HL), n    : mop_m1, uop_nop, mop_load_immediate(W), mop_store_indirect(W, HL)
LD (IX+d), n  : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), mop_load_immediate(W), uop_nop, uop_nop, uop_nop, mop_store_indirect(W, HL)
LD (IY+d), n  : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), mop_load_immediate(W), uop_nop, uop_nop, uop_nop, mop_store_indirect(W, HL)
LD A, (BC)    : mop_m1, uop_nop, mop_load_indirect(A, BC)
LD A, (DE)    : mop_m1, uop_nop, mop_load_indirect(A, DE)
LD A, (nn)    : mop_m1, uop_nop, mop_load_immediate(W), mop_load_immediate(Z), mop_load_indirect(A, ZW)
LD (BC), A    : mop_m1, uop_nop, mop_store_indirect(A, BC)
LD (DE), A    : mop_m1, uop_nop, mop_store_indirect(A, DE)
LD (nn), A    : mop_m1, uop_nop, mop_load_immediate(W), mop_load_immediate(Z), mop_store_indirect(A, ZW)
LD A, I       : mop_m1, uop_nop, mop_m1, uop_nop, uopalu(opMOV, A, I)
LD A, R       : mop_m1, uop_nop, mop_m1, uop_nop, uopalu(opMOV, A, R)
LD I, A       : mop_m1, uop_nop, mop_m1, uop_nop, uopalu(opMOV, I, A)
LD R, A       : mop_m1, uop_nop, mop_m1, uop_nop, uopalu(opMOV, R, A)
================ 16-bit load group ==============
LD dd, nn     : mop_m1, uop_nop, mop_load_immedate(get_low_reg(dd)), mop_load_immedate(get_high_reg(dd))
--- these three can probably be combined ---
LD IX, nn     : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immedate(IXl), mop_load_immedate(IXh)
LD IY, nn     : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immedate(IYl), mop_load_immedate(IYh)
LD HL, nn     : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immedate(HLl), mop_load_immedate(HLh)
LD dd, (nn)   : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immedate(TEMPl), mop_load_immedate(TEMPh), mop_load_indirect16(dd, TEMP)
LD IX, (nn)   : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immedate(TEMPl), mop_load_immedate(TEMPh), mop_load_indirect16(IX, TEMP)
LD IY, (nn)   : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immedate(TEMPl), mop_load_immedate(TEMPh), mop_load_indirect16(IY, TEMP)
LD (nn), dd   : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immedate(TEMPl), mop_load_immediate(TEMPh), mop_store_indirect16(dd, TEMP)
--- these three can probably be combined ---
LD (nn), HL   : mop_m1, uop_nop, mop_load_immedate(TEMPl), mop_load_immediate(TEMPh), mop_store_indirect16(HL, TEMP)
LD (nn), IX   : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immedate(TEMPl), mop_load_immediate(TEMPh), mop_store_indirect16(IX, TEMP)
LD (nn), IY   : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immedate(TEMPl), mop_load_immediate(TEMPh), mop_store_indirect16(IY, TEMP)
LD SP, HL     : mop_m1, uop_nop, uop_alu(opMOV, L, SPl), uop_alu(opMOV, H, SPh)
LD SP, IX     : mop_m1, uop_nop, mop_m1, uop_nop, uop_alu(opMOV, L, SPl), uop_alu(opMOV, H, SPh)
LD SP, IY     : mop_m1, uop_nop, mop_m1, uop_nop, uop_alu(opMOV, L, SPl), uop_alu(opMOV, H, SPh)
--- These 6 have the wrong timing, even though the total number of cycles works out. Maybe that's OK...
PUSH qq       : mop_m1, uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0 fTEMP), mop_store_indirect(get_low_reg(qq), SP), uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0, fTEMP), mop_store_indirect(get_high_reg(qq), SP)
PUSH IX       : mop_m1, uop_nop, mop_m1, uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0 fTEMP), mop_store_indirect(IXl, SP), uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0, fTEMP), mop_store_indirect(IXh, SP)
PUSH IY       : mop_m1, uop_nop, mop_m1, uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0 fTEMP), mop_store_indirect(IYl, SP), uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0, fTEMP), mop_store_indirect(IYh, SP)
POP qq        : mop_m1, mop_load_indirect(get_low_reg(qq), SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0 fTEMP), mop_load_indirect(get_high_reg(qq), SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0, fTEMP)
POP IX        : mop_m1, uop_nop, mop_m1, mop_load_indirect(IXl, SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0 fTEMP), mop_load_indirect(IXh, SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0, fTEMP)
POP IY        : mop_m1, uop_nop, mop_m1, mop_load_indirect(IYl, SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0 fTEMP), mop_load_indirect(IYh, SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0, fTEMP)
================ Exchange, Block Transfer, and Search Group ================
EX DE, HL     : mop_m1, uop_exchange_de_hl
EX AF, AF'    : mop_m1, uop_exchange_af
EXX           : mop_m1, uop_exchange_bcdehl
EX (SP), HL   : mop_m1, uop_nop, mop_load_indirect16(ZW, SP), uop_nop, mop_store_indirect16(HL, SP), uop_alu(opMOV, Z, get_high_reg(HL)), uop_alu(opMv, W, get_low_reg(HL))
EX (SP), IX   : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect16(ZW, SP), uop_nop, mop_store_indirect16(HL, SP), uop_alu(opMOV, Z, get_high_reg(HL)), uop_alu(opMv, W, get_low_reg(HL))
EX (SP), IY   : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect16(ZW, SP), uop_nop, mop_store_indirect16(HL, SP), uop_alu(opMOV, Z, get_high_reg(HL)), uop_alu(opMv, W, get_low_reg(HL))
LDI           : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(Z, HL, post_inc=True), uop_nop, mop_store_indirect(Z, DE, post_inc=True), mop_dec_bc, uop_nop
LDIR          : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(Z, HL, post_inc=True), uop_nop, mop_store_indirect(Z, DE, post_inc=True), mop_dec_bc, uop_endif(fPV), mop_dec16(pc, fTEMP), mop_dec16(pc, fTEMP), uop_nop
LDD           : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(Z, HL, post_dec=True), uop_nop, mop_store_indirect(Z, DE, post_dec=True), mop_dec_bc, uop_nop
LDDR          : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(Z, HL, post_dec=True), uop_nop, mop_store_indirect(Z, DE, post_dec=True), mop_dec_bc, uop_endif(fPV), mop_dec16(pc, fTEMP), mop_dec16(pc, fTEMP), uop_nop
CPI           : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(Z, HL, post_inc=True), uop_alu(opCP, A, Z, Flags), uop_nop * 5
CPIR          : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(Z, HL, post_inc=True), uop_alu(opCP, A, Z, Flags), uop_nop * 4, uop_endif(fPV), mop_dec16(pc, fTEMP), mop_dec16(pc, fTEMP), uop_nop
CPD           : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(Z, HL, post_dec=True), uop_alu(opCP, A, Z, Flags), uop_nop * 5
CPDR          : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(Z, HL, post_dec=True), uop_alu(opCP, A, Z, Flags), uop_nop * 4, uop_endif(fPV), mop_dec16(pc, fTEMP), mop_dec16(pc, fTEMP), uop_nop
================ 8-bit arithmetic Group ================
ADD/ADC/SUB/SBC/AND/OR/XOR/CP A, r       : mop_m1, uop_alu(opXXX, A, r, A, Flags)
ADD/ADC/SUB/SBC/AND/OR/XOR/CP A, n       : mop_m1, uop_nop, mop_load_immediate(Z), uop_alu(opXXX, A, Z, A, Flags)
ADD/ADC/SUB/SBC/AND/OR/XOR/CP A, (HL)    : mop_m1, uop_nop, mop_load_indirect(Z, HL), uop_alu(opXXX, A, Z, A, Flags)
ADD/ADC/SUB/SBC/AND/OR/XOR/CP A, (IX+d)  : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, uop_nop, uop_nop, mop_load_indirect(r, HL), uop_alu(opXXX, A, Z, A, Flags)
ADD/ADC/SUB/SBC/AND/OR/XOR/CP A, (IY+d)  : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, uop_nop, uop_nop, mop_load_indirect(r, HL), uop_alu(opXXX, A, Z, A, Flags)
INC/DEC r     : mop_m1, uop_alu(opXXX, r, r, Flags)
INC/DEC (HL)  : mop_m1, uop_nop, mop_load_indirect(Z, HL), uop_alu(opXXX, Z, Z, Flags), mop_store_indirect(Z, HL), uop_nop
INC/DEC (IX+d): mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, mop_load_indirect(Z, HL), uop_alu(opXXX, Z, Z, Flags), mop_store_indirect(Z, HL), uop_nop, uop_nop, uop_nop, uop_nop
INC/DEC (IY+d): mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, mop_load_indirect(Z, HL), uop_alu(opXXX, Z, Z, Flags), mop_store_indirect(Z, HL), uop_nop, uop_nop, uop_nop, uop_nop
================ General-Purpose Arithmetic and CPU Control Groups ================
DAA/CPL/NEG   : mop_m1, uop_alu(opXXX, A, A, Flags)
NOP           : mop_m1, uop_nop
CCF/SCF       : mop_m1, uop_alu(opXXX, None, None, Flags)
--- This has 3 extra clock cycles compared to the datasheet ---
HALT          : mop_m1, mop_dec16(pc, fTEMP), mop_dec16(pc, fTEMP)
DI            : mop_m1, uop_di
EI            : mop_m1, uop_ei
IM x          : mop_m1, uop_nop, mop_m1, uop_mx(x)
================ 16-bit Arithmetic group ================
ADD HL, ss    : mop_m1, uop_nop, uop_alu(opADD, get_low_reg(HL), get_low_reg(ss), get_low_reg(HL), Flags), uop_alu(opADC, get_high_reg(HL), get_high_reg(ss), get_high_reg(HL), Flags), uop_nop * 5
ADC HL, ss    : mop_m1, uop_nop, uop_alu(opADC, get_low_reg(HL), get_low_reg(ss), get_low_reg(HL), Flags), uop_alu(opADC, get_high_reg(HL), get_high_reg(ss), get_high_reg(HL), Flags), uop_nop * 5
SBC HL, ss    : mop_m1, uop_nop, uop_alu(opSBC, get_low_reg(HL), get_low_reg(ss), get_low_reg(HL), Flags), uop_alu(opSBC, get_high_reg(HL), get_high_reg(ss), get_high_reg(HL), Flags), uop_nop * 5
ADD IX, ss    : mop_m1, uop_nop, mop_m1, uop_nop, uop_alu(opADD, get_low_reg(HL), get_low_reg(ss), get_low_reg(HL), Flags), uop_alu(opADC, get_high_reg(HL), get_high_reg(ss), get_high_reg(HL), Flags), uop_nop * 5
ADD IY, ss    : mop_m1, uop_nop, mop_m1, uop_nop, uop_alu(opADD, get_low_reg(HL), get_low_reg(ss), get_low_reg(HL), Flags), uop_alu(opADC, get_high_reg(HL), get_high_reg(ss), get_high_reg(HL), Flags), uop_nop * 5
INC ss        : mop_m1, uop_nop, uop_alu(opADD, get_low_reg(ss), 1, get_low_reg(ss), fTemp), uop_alu(opADC, get_high_reg(ss), 0, get_high_reg(ss), fTemp)
INC IX        : mop_m1, uop_nop, mop_m1, uop_nop, uop_alu(opADD, get_low_reg(ss), 1, get_low_reg(ss), fTemp), uop_alu(opADC, get_high_reg(ss), 0, get_high_reg(ss), fTemp)
INC IY        : mop_m1, uop_nop, mop_m1, uop_nop, uop_alu(opADD, get_low_reg(ss), 1, get_low_reg(ss), fTemp), uop_alu(opADC, get_high_reg(ss), 0, get_high_reg(ss), fTemp)
DEC ss        : mop_m1, uop_nop, uop_alu(opSUB, get_low_reg(ss), 1, get_low_reg(ss), fTemp), uop_alu(opSBC, get_high_reg(ss), 0, get_high_reg(ss), fTemp)
DEC IX        : mop_m1, uop_nop, mop_m1, uop_nop, uop_alu(opSUB, get_low_reg(ss), 1, get_low_reg(ss), fTemp), uop_alu(opSBC, get_high_reg(ss), 0, get_high_reg(ss), fTemp)
DEC IY        : mop_m1, uop_nop, mop_m1, uop_nop, uop_alu(opSUB, get_low_reg(ss), 1, get_low_reg(ss), fTemp), uop_alu(opSBC, get_high_reg(ss), 0, get_high_reg(ss), fTemp)
================ Rotate and shift group ================
RLCA/RLA/RRCA/RRA                    : mop_m1, uop_alu(opXXX, A, A, Flags)
RLC/RL/RRC/RR/SLA/SLL/SRA/SRL r      : mop_m1, uop_nop, mop_m1, uop_alu(opXXX, r, r, Flags)
RLC/RL/RRC/RR/SLA/SLL/SRA/SRL (HL)   : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(W, HL), uop_alu(opXXX, W, W, Flags), mop_store_indirect(W, HL), uop_nop
RLC/RL/RRC/RR/SLA/SLL/SRA/SRL (IX+d) : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, mop_m1, mop_load_indirect(W, HL), uop_alu(opXXX, W, W, Flags), mop_store_indirect(W, HL), uop_nop
RLC/RL/RRC/RR/SLA/SLL/SRA/SRL (IX+d) : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, mop_m1, mop_load_indirect(W, HL), uop_alu(opXXX, W, W, Flags), mop_store_indirect(W, HL), uop_nop
RLD/RDD                              : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(W, HL), uop_mv_a_to_flags, uop_alu(opXXX, W, A, Flags) * 4, mop_store_indirect(W, HL), uop_mv_flags_to_a
================ Bit Set, Reset and Test Group ================
BIT b, r          : mop_m1, uop_nop, mop_m1, uop_alu(opBIT, r, b, Flags)
BIT b, (HL)       : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(W, HL), uop_nop, uop_alu(opBIT, W, b, Flags)
BIT b, (IX+d)     : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(W, HL), uop_nop, uop_alu(opBIT, W, b, Flags)
BIT b, (IY+d)     : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immediate(Z), uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(W, HL), uop_nop, uop_alu(opBIT, W, b, Flags)
SET/RES b, r      : mop_m1, uop_nop, mop_m1, uop_alu(opXXX, r, b, Flags)
SET/RES b, (HL)   : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(W, HL), uop_nop, uop_alu(opXXX, W, b, Flags), mop_store_indirect(W, HL)
SET/RES b, (IX+d) : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immedate(Z), uop_nop, mop_m1, uop_nop, mop_load_indirect(W, HL), uop_nop, uop_alu(opXXX, W, b, Flags), mop_store_indirect(W, HL)
SET/RES b, (IY+d) : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_immedate(Z), uop_nop, mop_m1, uop_nop, mop_load_indirect(W, HL), uop_nop, uop_alu(opXXX, W, b, Flags), mop_store_indirect(W, HL)
================ Jump Group ================
JP nn             : mop_m1, uop_nop, mop_load_immedate16(PC)
JP cc, nn         : mop_m1, uop_set_if(cc, target_reg=PC, target_reg=ZW), mop_load_immedate16(target_reg)
JR e              : mop_m1, uop_nop, mop_load_immedate(Z), uop_nop, uop_alu(opADD, get_low_reg(PC), Z, get_log_reg(PC), fTemp), uop_alu(opSEC, get_low_reg(PC), Z, get_log_reg(PC), fTemp), uop_nop * 3
JR C/NC/Z/NZ e    : mop_m1, uop_nop, mop_load_immedate(Z), uop_endif(cc), uop_alu(opADD, get_low_reg(PC), Z, get_log_reg(PC), fTemp), uop_alu(opSEC, get_high_reg(PC), Z, get_high_reg(PC), fTemp), uop_nop * 3
--- These three take an extra clock cycle compared to datasheet ---
JP (HL)           : mop_m1, uop_alu(opMOV, get_low_reg(HL), get_low_reg(PC)), uop_alu(opMOV, get_high_reg(HL), get_high_reg(PC))
JP (IX)           : mop_m1, uop_nop, mop_m1, uop_alu(opMOV, get_low_reg(HL), get_low_reg(PC)), uop_alu(opMOV, get_high_reg(HL), get_high_reg(PC))
JP (IY)           : mop_m1, uop_nop, mop_m1, uop_alu(opMOV, get_low_reg(HL), get_low_reg(PC)), uop_alu(opMOV, get_high_reg(HL), get_high_reg(PC))
DJNZ, e           : mop_m1, uop_alu(opDEC, B), mop_load_immedate(Z), uop_endif(cc), uop_alu(opADD, get_low_reg(PC), Z, get_log_reg(PC), fTemp), uop_alu(opSEC, get_high_reg(PC), Z, get_high_reg(PC), fTemp), uop_nop * 3
================ Call and Return Group ================
CALL nn           : mop_m1, uop_nop, mop_load_immedate(Z), uop_nop, mop_load_immediate(W), uop_alu(opSUB, SP, 1, SP, fTEMP), uop_alu(opSBC, SP, 0, SP, fTEMP), uop_address_phase(SP, post_dec, SP), uop_mem_write(PCh, addr_high_dec, SP), uop_alu(opMOV, W, PCh), mop_store_indirect(PCl, SP), uop_alu(opMOV, Z, PCl)
--- this is one cycle longer then datasheet ---
CALL cc, nn       : mop_m1, uop_nop, mop_load_immedate(Z), uop_nop, mop_load_immediate(W), uop_endif(cc) uop_alu(opSUB, SP, 1, SP, fTEMP), uop_alu(opSBC, SP, 0, SP, fTEMP), uop_address_phase(SP, post_dec, SP), uop_mem_write(PCh, addr_high_dec, SP), uop_alu(opMOV, W, PCh), mop_store_indirect(PCl, SP), uop_alu(opMOV, Z, PCl)
RET               : mop_m1, uop_nop, mop_load_indirect16(PC, SP, post_inc), uop_nop
RET cc            : mop_m1, uop_nop, uop_endif(cc), mop_load_indirect16(PC, SP, post_inc), uop_nop
RETI              : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect16(PC, SP, post_inc), uop_reti
RETN              : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect16(PC, SP, post_inc), uop_retn
RST p             : mop_m1, uop_alu(opSUB, SP, 1, SP, fTEMP), uop_alu(opSBC, SP, 0, SP, fTEMP), uop_address_phase(SP, post_dec, SP), uop_mem_write(PCh, addr_high_dec, SP), uop_alu(opMOV, 0, PCh), mop_store_indirect(PCl, SP), uop_alu(opMOV, p*8, PCl)
================ Input and Output Group ================
IN A, (n)         : mop_m1, uop_nop, mop_load_immediate(W), uop_alu(opMOV, A, Z), mop_load_indirect(A, ZW, io, extra_wait), uop_nop
IN r, (C)         : mop_m1, uop_nop, mop_m1, uop_nop, mop_load_indirect(r, BC, io, extra_wait), uop_nop
INI               : mop_m1, uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(Z, BC, io, post_inc=False, extra_wait), uop_nop, mop_store_indirect(Z, HL, post_inc=True), uop_alu(opSUB, B, 1, B), uop_nop
INIR              : mop_m1, uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(Z, BC, io, post_inc=False, extra_wait), uop_nop, mop_store_indirect(Z, HL, post_inc=True), uop_alu(opSUB, B, 1, B), uop_endif(fPV), mop_dec16(pc, fTEMP), mop_dec16(pc, fTEMP), uop_nop
IND               : mop_m1, uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(Z, BC, io, post_inc=False, extra_wait), uop_nop, mop_store_indirect(Z, HL, post_dec=True), uop_alu(opSUB, B, 1, B), uop_nop
INDR              : mop_m1, uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(Z, BC, io, post_inc=False, extra_wait), uop_nop, mop_store_indirect(Z, HL, post_dec=True), uop_alu(opSUB, B, 1, B), uop_endif(fPV), mop_dec16(pc, fTEMP), mop_dec16(pc, fTEMP), uop_nop
OUT (n), A        : mop_m1, uop_nop, mop_load_immediate(W), uop_alu(opMOV, A, Z), mop_store_indirect(A, ZW, io, extra_wait), uop_nop
OUT r, (C)        : mop_m1, uop_nop, mop_m1, uop_nop, mop_store_indirect(r, BC, io, extra_wait), uop_nop
OUTI              : mop_m1, uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(Z, HL, post_inc=True), uop_nop, mop_store_indirect(Z, BC, io, post_inc=False, extra_wait), uop_alu(opSUB, B, 1, B),
--- this is an extra cycle long ---
OTIR              : mop_m1, uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(Z, HL, post_inc=True), uop_nop, mop_store_indirect(Z, BC, io, post_inc=False, extra_wait), uop_alu(opSUB, B, 1, B), uop_endif(fPV), mop_dec16(pc, fTEMP), mop_dec16(pc, fTEMP), uop_nop
OUTD              : mop_m1, uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(Z, HL, post_dec=True), uop_nop, mop_store_indirect(Z, BC, io, post_inc=False, extra_wait), uop_alu(opSUB, B, 1, B),
--- this is an extra cycle long ---
OTDR              : mop_m1, uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(Z, HL, post_dec=True), uop_nop, mop_store_indirect(Z, BC, io, post_inc=False, extra_wait), uop_alu(opSUB, B, 1, B), uop_endif(fPV), mop_dec16(pc, fTEMP), mop_dec16(pc, fTEMP), uop_nop



Problematic instructions:
=========================
--- These 6 have the wrong timing, even though the total number of cycles works out. Maybe that's OK...
Problem is that we need to pre-decrement a 16-bit value twice, which is not possible. So a single-cycle 16-bit decrementer (and a 16-bit write-port) would help
(5, 3, 3)             PUSH qq       : mop_m1, uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0 fTEMP), mop_store_indirect(get_low_reg(qq), SP), uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0, fTEMP), mop_store_indirect(get_high_reg(qq), SP)
(4, 5, 3, 3)          PUSH IX       : mop_m1, uop_nop, mop_m1, uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0 fTEMP), mop_store_indirect(IXl, SP), uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0, fTEMP), mop_store_indirect(IXh, SP)
(4, 5, 3, 3)          PUSH IY       : mop_m1, uop_nop, mop_m1, uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0 fTEMP), mop_store_indirect(IYl, SP), uop_alu(opSUB, SPl, 1, fTEMP), uop_alu(opSBC, SPh, 0, fTEMP), mop_store_indirect(IYh, SP)
(4, 3, 3)             POP qq        : mop_m1, mop_load_indirect(get_low_reg(qq), SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0 fTEMP), mop_load_indirect(get_high_reg(qq), SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0, fTEMP)
(4, 4, 3, 3)          POP IX        : mop_m1, uop_nop, mop_m1, mop_load_indirect(IXl, SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0 fTEMP), mop_load_indirect(IXh, SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0, fTEMP)
(4, 4, 3, 3)          POP IY        : mop_m1, uop_nop, mop_m1, mop_load_indirect(IYl, SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0 fTEMP), mop_load_indirect(IYh, SP), uop_alu(opADD, SPl, 1, fTEMP), uop_alu(opADC, SPh, 0, fTEMP)
--- This has 1 extra clock cycles compared to the datasheet ---
Problem is that we need to decrement a 16-bit value in a single cycle. A single-cycle 16-bit decrementer (and a 16-bit write-port) would help
(4)                   HALT          : mop_m1, mop_dec16(pc, fTEMP)
--- These three take an extra clock cycle compared to datasheet ---
Problem is that we need to load a 16-bit entitity in a single cycle. So a 16-bit write port would help
(4)                   JP (HL)       : mop_m1, uop_alu(opMOV, get_low_reg(HL), get_low_reg(PC)), uop_alu(opMOV, get_high_reg(HL), get_high_reg(PC))
(4, 4)                JP (IX)       : mop_m1, uop_nop, mop_m1, uop_alu(opMOV, get_low_reg(HL), get_low_reg(PC)), uop_alu(opMOV, get_high_reg(HL), get_high_reg(PC))
(4, 4)                JP (IY)       : mop_m1, uop_nop, mop_m1, uop_alu(opMOV, get_low_reg(HL), get_low_reg(PC)), uop_alu(opMOV, get_high_reg(HL), get_high_reg(PC))
--- this is one cycle longer then datasheet ---
Problem is that we need to decrement a 16-bit value in a single cycle. A single-cycle 16-bit decrementer (and a 16-bit write-port) would help
(4, 3, 3+~1, ~3, ~3)  CALL cc, nn   : mop_m1, uop_nop, mop_load_immedate(Z), uop_nop, mop_load_immediate(W), uop_endif(cc) uop_alu(opSUB, SPl, 1, SPl, fTEMP), uop_alu(opSBC, SPh, 0, SPh, fTEMP), uop_address_phase(SP, post_dec, SP), uop_mem_write(PCh, addr_high_dec, SP), uop_alu(opMOV, W, PCh), mop_store_indirect(PCl, SP), uop_alu(opMOV, Z, PCl)
--- this is an extra cycle long ---
Problem is that post-decrement on mop_store_indirect doesn't support 8-bit decrements. This is not a true issue, it could be supported
(4, 5, 3, 4, ~5)      OTIR          : mop_m1, uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(Z, HL, post_inc=True), uop_nop, mop_store_indirect(Z, BC, io, post_inc=False, extra_wait), uop_alu(opSUB, B, 1, B), uop_endif(fPV), mop_dec16(pc, fTEMP), mop_dec16(pc, fTEMP), uop_nop
--- this is an extra cycle long ---
(4, 5, 3, 4, ~5)      OTDR          : mop_m1, uop_nop, mop_m1, uop_nop, uop_nop, mop_load_indirect(Z, HL, post_dec=True), uop_nop, mop_store_indirect(Z, BC, io, post_inc=False, extra_wait), uop_alu(opSUB, B, 1, B), uop_endif(fPV), mop_dec16(pc, fTEMP), mop_dec16(pc, fTEMP), uop_nop


OVERALL, TO MAKE THE WHOLE CORE CYCLE-ACCURATE WE NEED:

- A 16-bit write port into the register file (at least to SP and PC)
- The ALU to support 16-bit INC/DEC in a single cycle


"""

'''
Another architecture then:

Register file notes:
--------------------
B , C
D , E
H , L
Z , A
F , W
B', C'
D', E'
H', L'
Z', A'
F', W'
I , R
IXh, IXl
IYh, IYl
SPh, SPl
PCh, PCl

BC, DE, HL --> first letter is high-byte, second letter is low-byte. Note: as far as the register file is concerned, any two register can form a 16-bit couple for reads at least

The register file also support 16-bit writes, but only in the sense that one left-side and one register pair can be written. Byte-enables are used
to support arbitrary byte-writes, if lower- and higher- 8-bits contain the same data.

This feature allows for single-cycle updates of BC, DE, HL, IX, IY, SP or PC (other combos are ZA and FW, which are not all that useful)

On top of all this, F/F' is always available for read/write on an independent bus.

ALTERNATIVE: 2 completely independent 8-bit write ports. This would allow for simple storage of ALU results (F, A).
ALTERNATIVE: we could swap the encoding of F and Z, which makes instruction decode a bit more complex, but allows for still a single 16-bit write port

TO INVESTIGATE: can we get away with no immediate access to F? It might be that when it's needed (loop instructions, conditionals, operations that leave certain bits unchanged) can afford the extra read.
   ALTERNATIVE: instead of storing F in the register file (or on top of it) we could have a cache copy, which gets written with F, but can be read independently. The cache would need to be changed whenever
                F/F' swap takes place, but would allow for more compact reg-file implementation (?)

NOTES:
- BRAM doesn't support async read ports.
- MLAB doesn't support independent read/write ports: It's single-ported.

Can we get away with a single-ported RF? Probably not. Especially since we need to do two reads in a single cycle!

That pretty much means the reg-file to be done in flops (yuck), but then port-config and what not is much less of an issue.

APB bus notes
-------------

Write is 2-cycles: where address (but not data) is presented in the first cycle, while both address and data is presented in the second.
   wait-states are checked in the second cycle only.

Read is also 2-cycles: address is presented in the first cycle, data is expected back on the second.
   wait-states are checked in the second cycle only.

This is actually *almost exactly* what the Z80 bus cycles looked like.

In order to support this, we would need to either:
- Able to read the address one-cycle early and load it into the address register
- Directly present the address from the reg-file in the first cycle and switch over to the address register on subsequent cycles.

ALU notes
---------

The current implementation assumes, we can:
- Read two registers
- Perform an ALU op
- Reach the write-target register
All in a single cycle.

The critical path through that is probably the carry-chain of a 16-bit inc/dec operation.

DECODE notes
------------
There's a useful (if incomplete) decode table here:
https://nanode0000.wordpress.com/2017/08/22/a-minimum-interactive-language-toolkit/

'''