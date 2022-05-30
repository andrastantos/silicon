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

"""
Register file notes:
--------------------
 WR addr | RD addr | High    Low
    0    |  0,   1 |  B,      C
    1    |  2,   3 |  D,      E
    2    |  4,   5 |  H,      L
    3    |  6,   7 |  Z,      A
    4    |  8,   9 |  F,      W
    5    | 10,  11 |  I,      R
    6    | 12,  13 |  IXh,    IXl
    7    | 14,  15 |  IYh,    IYl
    8    | 16,  17 |  SPh,    SPl
    9    | 18,  19 |  PCh,    PCl
 Not directly addressable:
                      B',     C'
                      D',     E'
                      H',     L'
                      Z',     A'
                      F',     W'

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
"""

class RegEn(Module):
    output_port = Output()
    input_port = Input()
    clock_port = ClkPort()
    reset_port = RstPort()
    reset_value_port = RstValPort()
    clock_en = ClkEnPort()

    def body(self):
        value = Wire(self.input_port.get_net_type())
        value <<= Reg(Select(self.clock_en, value, self.input_port))
        self.output_port <<= value
'''
RegEn = Reg
'''

class Z80RegFile(Module):
    clk = ClkPort()
    clk_en = Input(logic)
    rst = RstPort()

    wr_a = Input(Unsigned(4))
    wr_l = Input(TByte)
    wr_l_valid = Input(logic)
    wr_h = Input(TByte)
    wr_h_valid = Input(logic)
    wr_f = Input(TByte)
    wr_f_valid = Input(logic)

    rd_a1 = Input(Unsigned(5))
    rd_d1 = Output(TByte)
    rd_a2 = Input(Unsigned(5))
    rd_d2 = Output(TByte)
    rd_f = Output(TByte)

    rdB = 0
    rdC = 1
    rdD = 2
    rdE = 3
    rdH = 4
    rdL = 5
    rdZ = 6 # Undocumented temp register. Used as a temporary result location in case of the DDCB prefix.
    rdA = 7
    rdF = 8 # Undocumented temp register. Can be used as a 16-bit temp register with Z
    rdW = 9
    rdI = 10
    rdR = 11
    rdIXh = 12
    rdIXl = 13
    rdIYh = 14
    rdIYl = 15
    rdSPh = 16
    rdSPl = 17
    rdPCh = 18
    rdPCl = 19

    wrBC = 0
    wrDE = 1
    wrHL = 2
    wrZA = 3
    wrFW = 4
    wrIR = 5
    wrIX = 6
    wrIY = 7
    wrSP = 8
    wrPC = 9
    exchange_af     = Input(logic)
    exchange_bcdehl = Input(logic)
    exchange_de_hl  = Input(logic)

    def body(self):
        self.rB   = Wire(TByte)
        self.rC   = Wire(TByte)
        self.rD   = Wire(TByte)
        self.rE   = Wire(TByte)
        self.rH   = Wire(TByte)
        self.rL   = Wire(TByte)
        self.rZ   = Wire(TByte)
        self.rA   = Wire(TByte)
        self.rF   = Wire(TByte)
        self.rW   = Wire(TByte)
        self.rI   = Wire(TByte)
        self.rR   = Wire(TByte)
        self.rIXh = Wire(TByte)
        self.rIXl = Wire(TByte)
        self.rIYh = Wire(TByte)
        self.rIYl = Wire(TByte)
        self.rSPh = Wire(TByte)
        self.rSPl = Wire(TByte)
        self.rPCh = Wire(TByte)
        self.rPCl = Wire(TByte)
        self.rBp  = Wire(TByte)
        self.rCp  = Wire(TByte)
        self.rDp  = Wire(TByte)
        self.rEp  = Wire(TByte)
        self.rHp  = Wire(TByte)
        self.rLp  = Wire(TByte)
        self.rZp  = Wire(TByte)
        self.rAp  = Wire(TByte)
        self.rFp  = Wire(TByte)
        self.rWp  = Wire(TByte)

        self.af_prime = Wire(logic)
        self.bcdehl_prime = Wire(logic)
        self.dehl_swap = Wire(logic)
        self.dehl_swap_prime = Wire(logic)

        self.af_prime <<= RegEn(Select(self.exchange_af, self.af_prime, ~self.af_prime))
        self.bcdehl_prime <<= RegEn(Select(self.exchange_bcdehl, self.bcdehl_prime, ~self.bcdehl_prime))
        self.dehl_swap <<= RegEn(Select(self.exchange_de_hl & ~self.bcdehl_prime, self.dehl_swap, ~self.dehl_swap))
        self.dehl_swap_prime <<= RegEn(Select(self.exchange_de_hl & self.bcdehl_prime, self.dehl_swap_prime, ~self.dehl_swap_prime))

        self.swap_de_hl = Wire(logic)
        self.swap_de_hl <<= Select(self.bcdehl_prime, self.dehl_swap, self.dehl_swap_prime)

        self.rB   <<= RegEn(Select((self.wr_a == Z80RegFile.wrBC                                          )  & self.wr_h_valid & ~self.bcdehl_prime, self.rB  , self.wr_h))
        self.rC   <<= RegEn(Select((self.wr_a == Z80RegFile.wrBC                                          )  & self.wr_l_valid & ~self.bcdehl_prime, self.rC  , self.wr_l))
        self.rD   <<= RegEn(Select((self.wr_a == Select(self.swap_de_hl, Z80RegFile.wrDE, Z80RegFile.wrHL))  & self.wr_h_valid & ~self.bcdehl_prime, self.rD  , self.wr_h))
        self.rE   <<= RegEn(Select((self.wr_a == Select(self.swap_de_hl, Z80RegFile.wrDE, Z80RegFile.wrHL))  & self.wr_l_valid & ~self.bcdehl_prime, self.rE  , self.wr_l))
        self.rH   <<= RegEn(Select((self.wr_a == Select(self.swap_de_hl, Z80RegFile.wrHL, Z80RegFile.wrDE))  & self.wr_h_valid & ~self.bcdehl_prime, self.rH  , self.wr_h))
        self.rL   <<= RegEn(Select((self.wr_a == Select(self.swap_de_hl, Z80RegFile.wrHL, Z80RegFile.wrDE))  & self.wr_l_valid & ~self.bcdehl_prime, self.rL  , self.wr_l))
        self.rZ   <<= RegEn(Select((self.wr_a == Z80RegFile.wrZA                                          )  & self.wr_h_valid & ~self.bcdehl_prime, self.rZ  , self.wr_h))
        self.rA   <<= RegEn(Select((self.wr_a == Z80RegFile.wrZA                                          )  & self.wr_l_valid & ~self.af_prime,     self.rA  , self.wr_l))
        self.rF   <<= RegEn(Select(self.wr_f_valid & ~self.af_prime, Select((self.wr_a == Z80RegFile.wrFW)   & self.wr_h_valid & ~self.af_prime,     self.rF  , self.wr_h), self.wr_f))
        self.rW   <<= RegEn(Select((self.wr_a == Z80RegFile.wrFW                                          )  & self.wr_l_valid & ~self.bcdehl_prime, self.rW  , self.wr_l))

        self.rBp  <<= RegEn(Select((self.wr_a == Z80RegFile.wrBC                                          ) & self.wr_h_valid & self.bcdehl_prime, self.rBp  , self.wr_h))
        self.rCp  <<= RegEn(Select((self.wr_a == Z80RegFile.wrBC                                          ) & self.wr_l_valid & self.bcdehl_prime, self.rCp  , self.wr_l))
        self.rDp  <<= RegEn(Select((self.wr_a == Select(self.swap_de_hl, Z80RegFile.wrDE, Z80RegFile.wrHL)) & self.wr_h_valid & self.bcdehl_prime, self.rDp  , self.wr_h))
        self.rEp  <<= RegEn(Select((self.wr_a == Select(self.swap_de_hl, Z80RegFile.wrDE, Z80RegFile.wrHL)) & self.wr_l_valid & self.bcdehl_prime, self.rEp  , self.wr_l))
        self.rHp  <<= RegEn(Select((self.wr_a == Select(self.swap_de_hl, Z80RegFile.wrHL, Z80RegFile.wrDE)) & self.wr_h_valid & self.bcdehl_prime, self.rHp  , self.wr_h))
        self.rLp  <<= RegEn(Select((self.wr_a == Select(self.swap_de_hl, Z80RegFile.wrHL, Z80RegFile.wrDE)) & self.wr_l_valid & self.bcdehl_prime, self.rLp  , self.wr_l))
        self.rZp  <<= RegEn(Select((self.wr_a == Z80RegFile.wrZA                                          ) & self.wr_h_valid & self.bcdehl_prime, self.rZp  , self.wr_h))
        self.rAp  <<= RegEn(Select((self.wr_a == Z80RegFile.wrZA                                          ) & self.wr_l_valid & self.af_prime,     self.rAp  , self.wr_l))
        self.rFp  <<= RegEn(Select(self.wr_f_valid & self.af_prime,  Select((self.wr_a == Z80RegFile.wrFW)  & self.wr_h_valid & self.af_prime,     self.rFp  , self.wr_h), self.wr_f))
        self.rWp  <<= RegEn(Select((self.wr_a == Z80RegFile.wrFW                                          ) & self.wr_l_valid & self.bcdehl_prime, self.rWp  , self.wr_l))

        self.rI   <<= RegEn(Select((self.wr_a == Z80RegFile.wrIR) & self.wr_h_valid, self.rI  , self.wr_h))
        self.rR   <<= RegEn(Select((self.wr_a == Z80RegFile.wrIR) & self.wr_l_valid, self.rR  , self.wr_l))
        self.rIXh <<= RegEn(Select((self.wr_a == Z80RegFile.wrIX) & self.wr_h_valid, self.rIXh, self.wr_h))
        self.rIXl <<= RegEn(Select((self.wr_a == Z80RegFile.wrIX) & self.wr_l_valid, self.rIXl, self.wr_l))
        self.rIYh <<= RegEn(Select((self.wr_a == Z80RegFile.wrIY) & self.wr_h_valid, self.rIYh, self.wr_h))
        self.rIYl <<= RegEn(Select((self.wr_a == Z80RegFile.wrIY) & self.wr_l_valid, self.rIYl, self.wr_l))
        self.rSPh <<= RegEn(Select((self.wr_a == Z80RegFile.wrSP) & self.wr_h_valid, self.rSPh, self.wr_h))
        self.rSPl <<= RegEn(Select((self.wr_a == Z80RegFile.wrSP) & self.wr_l_valid, self.rSPl, self.wr_l))
        self.rPCh <<= RegEn(Select((self.wr_a == Z80RegFile.wrPC) & self.wr_h_valid, self.rPCh, self.wr_h))
        self.rPCl <<= RegEn(Select((self.wr_a == Z80RegFile.wrPC) & self.wr_l_valid, self.rPCl, self.wr_l))

        def read_logic(addr):
            return Select(addr,
                Select(self.bcdehl_prime, self.rB, self.rBp),
                Select(self.bcdehl_prime, self.rC, self.rCp),
                Select(self.bcdehl_prime, Select(self.swap_de_hl, self.rD, self.rH), Select(self.swap_de_hl, self.rDp, self.rHp)),
                Select(self.bcdehl_prime, Select(self.swap_de_hl, self.rE, self.rL), Select(self.swap_de_hl, self.rEp, self.rLp)),
                Select(self.bcdehl_prime, Select(self.swap_de_hl, self.rH, self.rD), Select(self.swap_de_hl, self.rHp, self.rDp)),
                Select(self.bcdehl_prime, Select(self.swap_de_hl, self.rL, self.rE), Select(self.swap_de_hl, self.rLp, self.rEp)),
                Select(self.bcdehl_prime, self.rZ, self.rZp),
                Select(self.af_prime, self.rA, self.rAp),
                Select(self.af_prime, self.rF, self.rFp),
                Select(self.bcdehl_prime, self.rW, self.rWp),
                self.rI,
                self.rR,
                self.rIXh,
                self.rIXl,
                self.rIYh,
                self.rIYl,
                self.rSPh,
                self.rSPl,
                self.rPCh,
                self.rPCl
            )

        self.rd_d1 <<= read_logic(self.rd_a1)
        self.rd_d2 <<= read_logic(self.rd_a2)

        self.rd_f = Select(self.af_prime, self.rF, self.rFp)

def test_verilog():
    test.rtl_generation(Z80RegFile, "z80_reg_file")

def test_sim():
    class Z80RegFile_tb(Z80RegFile):
        # Some virtual 16-bit read values
        rdBC = 0
        rdDE = 2
        rdHL = 4
        rdZA = 6
        rdFW = 8
        rdIR = 10
        rdIX = 12
        rdIY = 14
        rdSP = 16
        rdPC = 18

        def simulate(self) -> TSimEvent:
            # NOTE: we're going to use rdXX register addresses for both reads and writes
            def clk() -> int:
                yield 10
                self.clk <<= ~self.clk & self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0

            def write_8(reg, value) -> None:
                self.wr_l_valid <<= reg & 1 == 1
                self.wr_h_valid <<= reg & 1 == 0
                self.wr_a <<= reg >> 1
                self.wr_l <<= value
                self.wr_h <<= value

            def write_16(reg, value) -> None:
                self.wr_l_valid <<= 1
                self.wr_h_valid <<= 1
                self.wr_a <<= reg >> 1
                self.wr_l <<= (value >> 0) & 0xff
                self.wr_h <<= (value >> 8) & 0xff

            def write_f(value) -> None:
                self.wr_f_valid <<= 1
                self.wr_f = value

            def end_write() -> None:
                self.wr_f_valid <<= 0
                self.wr_l_valid <<= 0
                self.wr_h_valid <<= 0

            def read_a(reg, expected_value) -> None:
                self.rd_a1 <<= reg
                yield 0
                assert self.rd_d1 == expected_value

            def read_b(reg, expected_value) -> None:
                self.rd_a2 <<= reg
                yield 0
                assert self.rd_d2 == expected_value

            def reg_to_str(reg, is_16_bit: bool = False) -> str:
                if is_16_bit:
                    return ("rdBC", "rdDE", "rdHL", "rdZA", "rdFW", "rdIR", "rdIX", "rdIY", "rdSP", "rdPC")[reg >> 1]
                else:
                    return ("rdB", "rdC", "rdD", "rdE", "rdH", "rdL", "rdZ", "rdA", "rdF", "rdW", "rdI", "rdR", "rdIXh", "rdIXl", "rdIYh", "rdIYl", "rdSPh", "rdSPl", "rdPCh", "rdPCl")[reg]

            def read_16(reg, expected_value) -> None:
                print(f"reading 16-bit register {reg_to_str(reg, True)}... ", end="", flush=True)
                self.rd_a1 <<= reg+1
                self.rd_a2 <<= reg
                yield 0
                val = self.rd_d2 << 8 | self.rd_d1
                if val == expected_value:
                    print(f"PASS")
                else:
                    print(f"returned {val:04x}, expected {expected_value:04x}")
                    assert False

            def read_f(expected_value) -> None:
                yield 0
                assert self.rd_f == expected_value

            print("Simulation started")
            self.clk_en <<= 1

            self.rst <<= 1
            self.clk <<= 1
            yield 10
            for i in range(5):
                yield from clk()
            self.rd_a1 <<= 0
            self.rd_a2 <<= 0
            self.wr_l_valid <<= 0
            self.wr_h_valid <<= 0
            self.wr_f_valid <<= 0
            self.exchange_af <<= 0
            self.exchange_bcdehl <<= 0
            self.exchange_de_hl <<= 0
            for i in range(5):
                yield from clk()
            self.rst <<= 0
            print(f"Init complete")

            write_16(self.rdBC, 0x0102)
            yield from clk()
            end_write()
            yield from read_16(self.rdBC, 0x0102)
            write_16(self.rdDE, 0x0304)
            yield from clk()
            end_write()
            write_16(self.rdHL, 0x0506)
            yield from clk()
            end_write()
            write_16(self.rdZA, 0x0708)
            yield from clk()
            end_write()
            yield from read_16(self.rdBC, 0x0102)
            yield from clk()
            yield from read_16(self.rdDE, 0x0304)
            yield from clk()
            yield from read_16(self.rdHL, 0x0506)
            yield from clk()
            yield from read_16(self.rdZA, 0x0708)
            yield from clk()
            write_16(self.rdFW, 0x090a)
            yield from clk()
            end_write()
            write_16(self.rdIR, 0x0b0c)
            yield from clk()
            end_write()
            write_16(self.rdIX, 0x0d0e)
            yield from clk()
            end_write()
            write_16(self.rdIY, 0x0f10)
            yield from clk()
            end_write()
            write_16(self.rdSP, 0x1112)
            yield from clk()
            end_write()
            write_16(self.rdPC, 0x1314)
            yield from clk()
            end_write()
            yield from read_16(self.rdBC, 0x0102)
            yield from clk()
            yield from read_16(self.rdDE, 0x0304)
            yield from clk()
            yield from read_16(self.rdHL, 0x0506)
            yield from clk()
            yield from read_16(self.rdZA, 0x0708)
            yield from clk()
            yield from read_16(self.rdFW, 0x090a)
            yield from clk()
            yield from read_16(self.rdIR, 0x0b0c)
            yield from clk()
            yield from read_16(self.rdIX, 0x0d0e)
            yield from clk()
            yield from read_16(self.rdIY, 0x0f10)
            yield from clk()
            yield from read_16(self.rdSP, 0x1112)
            yield from clk()
            yield from read_16(self.rdPC, 0x1314)
            yield from read_f(0x09)
            yield from clk()

            write_8(self.rdPCl, 0xf0)
            yield from read_16(self.rdPC, 0x1314)
            yield from clk()
            end_write()
            yield from read_16(self.rdPC, 0x13f0)
            yield from clk()


            write_8(self.rdA, 0xff)
            yield from read_16(self.rdZA, 0x0708)
            yield from clk()
            end_write()
            yield from read_16(self.rdZA, 0x07ff)
            yield from clk()

            write_f(0xfe)
            yield from read_f(0x09)
            yield from clk()
            end_write()
            yield from read_16(self.rdFW, 0xfe0a)
            yield from read_f(0xfe)
            yield from clk()


            for i in range(5):
                yield from clk()

            print(f"Done")

    test.simulation(Z80RegFile_tb, "z80_reg_file")

if __name__ == "__main__":
    test_sim()
    #test_verilog()
