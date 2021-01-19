#!/usr/bin/python3
# Good documents https://cpctech.cpc-live.com/docs.html

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".." / ".."))
sys.path.append(str(Path(__file__).parent / ".." / ".." / "unit_tests"))

from typing import *

from silicon import *
from test_utils import *
import inspect

TByte = Unsigned(length=8)

class timing(Module):
    rst = Input(logic)
    clk = Input(logic) # 16MHz clock input

    # The phase relationship between these three clocks is important, though TBD.
    cclk = Output(logic) # clock to CCRT, but also user as A0 for memory addressing, allowing 16-bits/character readout from memory. This is a 1MHz 50% duty-cycle clock
    phi_clk_en = Output(logic) # 4MHz clock to the CPU. This is a 4MHz, 12.5% duty-cycle clock
    n_cpu = Output(logic) # 1MHz clock it seems, though it's also used to mux the memory between the Z80 and the CCRT
    ready = Output(logic) # Has something to do with disconnection the Z80 from the DRAM data-bus (CPU read direction)
    # The phase relationship between the two 1MHz clocks is described here:
    # https://retrocomputing.stackexchange.com/questions/919/memory-sharing-mechanism-in-the-amstrad-cpc-computer
    # Apparently READY (nWAIT on the Z80) is also a 1MHz clock (maybe?)
    # The phase relationships are as follows (I think):
    #
    #           | 0 | 1 | 2 | 3 | 0 | 1 | 2 |
    #            _   _   _   _   _   _   _   _
    # phi_clk: _/ \_/ \_/ \_/ \_/ \_/ \_/ \_/
    #
    # bus user: <-CPU -><-CCRT-><-CPU -><-CCRT->
    #            ___             ___
    # ready:   _/   \___________/   \________
    #          _         _______         ____
    # n_cpu:    \_______/       \_______/
    #          _____         _______
    # cclk:         \_______/       \_______/
    #
    # Now, that's all nice and dandy, but we're actually using clock-enables to drive the various circuits in our system.
    # That means that on top of these clocks (as all but phy are also used as logic signals) we also have to generate
    # single-clock enables at the right frequencies (phase doesn't matter at that point)
    clk_1mhz_en = Output(logic) # 1MHz clock enable
    def body(self):
        self.prescaler = Wire(Unsigned(length=4))
        self.prescaler <<= Reg((self.prescaler + 1)[3:0])

        self.cclk_reg = Wire(logic)
        self.cclk_reg <<= Reg(self.prescaler[3] == self.prescaler[2])
        self.cclk <<= self.cclk_reg

        self.n_cpu_reg = Wire(logic)
        self.n_cpu_reg <<= Reg(self.prescaler[3])
        self.n_cpu <<= self.n_cpu_reg

        self.ready_reg = Wire(logic)
        self.ready_reg <<= Reg(self.prescaler[3:2] == 0)
        self.ready <<= self.ready_reg

        self.phi_clk_en_reg = Wire(logic)
        self.phi_clk_en_reg <<= Reg(self.prescaler[1:0] == 0)
        self.phi_clk_en <<= self.phi_clk_en_reg

        self.clk_1mhz_en_reg = Wire(logic)
        self.clk_1mhz_en_reg <<= Reg(self.prescaler == 0)
        self.clk_1mhz_en <<= self.clk_1mhz_en_reg 

def test_verilog():
    test.rtl_generation(timing, "timing")

def test_sim():
    class timing_tb(timing):
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

            yield from clk()
            self.rst = 0
            for i in range(50):
                now = yield from clk()

            print(f"Done at {now}")

    test.simulation(timing_tb)

if __name__ == "__main__":
    #test_verilog()
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