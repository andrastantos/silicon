#!/usr/bin/python3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".."))
sys.path.append(str(Path(__file__).parent / ".."/ "unit_tests"))

from typing import *

from silicon import *
from test_utils import *
import inspect

TByte = Unsigned(length=8)

class mc6845(Module):
    rst = ClkPort()
    clk = RstPort()

    n_cs = Input(logic)
    data_in = Input(logic)

    def body(self):
        wr_idx = ~self.n_cs

        r_feedback = Wire(logic)
        xxxxx = Select(wr_idx, r_feedback, self.data_in)
        r_feedback <<= Reg(xxxxx)
        r_direct = Reg(self.n_cs)
        r_delayed = Reg(wr_idx)

def test_sim():
    class mc6845_tb(mc6845):
        def simulate(self) -> TSimEvent:
            self.pclk_cnt = 0
            def clk() -> int:
                yield 10
                self.clk = ~self.clk
                yield 10
                self.clk = ~self.clk
                yield 0

            print("Simulation started")
            self.rst = 0
            self.clk = 1
            yield 10
            yield from clk()
            self.bus_en = 0
            self.n_cs = 1
            yield from clk()
            self.n_cs = 0
            print(f"Done")

    test.simulation(mc6845_tb, "test_sequential")

if __name__ == "__main__":
    #test_verilog()
    test_sim()
