import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".." / ".."))
sys.path.append(str(Path(__file__).parent / ".." / ".." / "unit_tests"))

from typing import *

from silicon import *
from test_utils import *


from fft import *



def test_butterfly_mem_verilog():
    test.rtl_generation(ButterflyMem(addr_len=8,level=4), "butterfly_mem")

'''
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
                self.clk <<= ~self.clk
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
                print(f"reading 16-bit register {reg_to_str(reg, True)}... ", end="", flush_in=True)
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
'''

if __name__ == "__main__":
    #test_sim()
    test_butterfly_mem_verilog()
