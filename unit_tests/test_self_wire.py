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

class test_self_wire(Module):
    n_cs = Input(logic)
    data_in = Input(TByte)
    data_out = Output(TByte)
    n_wr = Input(logic)
    clk = ClkPort()
    rst = RstPort()

    def body(self):
        # Register file
        self.r0_horizontal_total = Wire(TByte)

        wr_en = ~self.n_cs & ~self.n_wr
        rd_en = ~self.n_cs & self.n_wr
        ddd = Select(wr_en , self.r0_horizontal_total, self.data_in)
        self.r0_horizontal_total      <<= Reg(ddd)
        self.data_out <<= Select(rd_en, self.r0_horizontal_total, 0)


def test_verilog():
    test.rtl_generation(test_self_wire, "test_self_wire")

def test_sim():
    class test_self_wire_tb(test_self_wire):
        def simulate(self) -> TSimEvent:
            def clk() -> int:
                yield 10
                self.clk = ~self.clk
                yield 10
                self.clk = ~self.clk

            print("Simulation started")
            self.rst = 1
            self.clk = 1
            yield 10
            for i in range(5):
                yield from clk()
            self.bus_en = 0
            self.n_cs = 1
            self.n_wr = None
            self.data_in = None

            yield from clk()
            self.rst = 0
            for i in range(5):
                yield from clk()

            def read() -> Optional[int]:
                # Select register by writing to the index
                self.n_cs = 0
                self.n_wr = 1
                self.data_in = None
                yield from clk()
                self.n_cs = 1
                self.n_wr = None
                return self.data_out.sim_value

            def write(data:int) -> None:
                # Write data into data register
                self.n_cs = 0
                self.n_wr = 0
                self.data_in = data
                yield from clk()
                self.n_cs = 1
                self.n_wr = None

            yield from write(14)
            yield from write(5)

            print(f"Register programmed")
            for i in range(5):
                now = yield from clk()

            print(f"Done at {now}")

    test.simulation(test_self_wire_tb, inspect.currentframe().f_code.co_name)

if __name__ == "__main__":
    test_verilog()
    test_sim()

"""
An idea from PyRTL: use <<= as the 'bind' operator. Could re-use the same for simulation assignment, though that's ugly. (not that the current hack isn't either)

Alternatives:
    PyRTL - https://ucsbarchlab.github.io/PyRTL/
    pyverilog - https://pypi.org/project/pyverilog/ <-- actually, no, this is a Verilog parser and co. in Python.
    pyMTL - https://github.com/cornell-brg/pymtl
    myHDL - http://www.myhdl.org/

    All of them seem to take the road of trying to understand and convert python to RTL as opposed to 'describe' RTL in python.
"""