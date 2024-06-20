#!/usr/bin/python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / ".."))

from typing import *

from silicon import *
import silicon
from test_utils import *
from random import seed, randint

import inspect

def test_round_robin_arbiter():
    class top(Module):
        def body(self):
            self.clk = Wire(logic)
            self.rst = Wire(logic)
            self.requestors = Wire(Unsigned(8))
            self.grants = Wire(Unsigned(8))
            self.advance = Wire(logic)

            dut = RoundRobinArbiter()
            self.grants <<= dut(self.requestors, self.advance)

        def simulate(self, simulator: Simulator):
            seed(0)
            def clk() -> int:
                yield 5
                self.clk <<= ~self.clk & self.clk
                yield 5
                self.clk <<= ~self.clk
                yield 0

            print("Simulation started")

            self.rst <<= 1
            self.clk <<= 1
            self.advance <<= 0
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0

            self.requestors <<= 0xff
            yield from clk()
            simulator.sim_assert(self.grants == 0x80)
            self.advance <<= 1
            for i in range(16):
                yield from clk()
                simulator.sim_assert(self.grants == (1 << (7-(i % 8))))

            for i in range(8):
                self.requestors <<= 1 << i
                for i in range(8):
                    yield from clk()
                    simulator.sim_assert(self.grants == self.requestors)

    test.simulation(top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)

def test_round_robin_arbiter_binary():
    class top(Module):
        def body(self):
            self.clk = Wire(logic)
            self.rst = Wire(logic)
            self.requestors = Wire(Unsigned(8))
            self.grants = Wire(Unsigned(3))
            self.advance = Wire(logic)

            dut = RoundRobinArbiter(RoundRobinArbiter.OutputKind.Binary)
            self.grants <<= dut(self.requestors, self.advance)

        def simulate(self, simulator: Simulator):
            seed(0)
            def clk() -> int:
                yield 5
                self.clk <<= ~self.clk & self.clk
                yield 5
                self.clk <<= ~self.clk
                yield 0

            print("Simulation started")

            self.rst <<= 1
            self.clk <<= 1
            self.advance <<= 0
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0

            self.requestors <<= 0xff
            yield from clk()
            simulator.sim_assert(self.grants == 7)
            self.advance <<= 1
            for i in range(16):
                yield from clk()
                simulator.sim_assert(self.grants == (7-(i % 8)))

            for i in range(8):
                self.requestors <<= 1 << i
                for j in range(8):
                    yield from clk()
                    simulator.sim_assert(self.grants == i)

    test.simulation(top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)


if __name__ == "__main__":
    #test_round_robin_arbiter()
    test_round_robin_arbiter_binary()