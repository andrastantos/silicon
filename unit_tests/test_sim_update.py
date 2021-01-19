#!/usr/bin/python3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".."))

from typing import *

from silicon import *
from test_utils import *
import inspect

def test_sim_update():
    class top(Module):
        n_rd = Input(logic)
        n_cs = Input(logic)
        addr = Input(logic)
        data_out = Output(Unsigned(length=8))

        def body(self):
            pa_sel = ~self.addr[0]
            pb_sel = self.addr[0]

            self.data_out = SelectOne(
                pa_sel & ~self.n_cs & ~self.n_rd, 0x11,
                pb_sel & ~self.n_cs & ~self.n_rd, 0x22
            )

        def simulate(self) -> TSimEvent:
            def clk() -> int:
                yield 10
                yield 10

            print("Simulation started")
            self.n_cs = 1
            self.n_rd = 1
            self.data_in = 0
            self.addr = 0
            yield from clk()
            
            def read(addr: int) -> Optional[int]:
                self.n_cs = 0
                self.n_rd = 0
                self.addr = addr
                yield from clk()
                #self.n_cs = 1
                self.n_rd = 1
                return self.data_out.sim_value

            pa_addr = 0
            pb_addr = 1
            data = yield from read(pa_addr)
            assert data == 0x11
            yield from clk()
            data = yield from read(pb_addr)
            assert data == 0x22
            data = yield from read(pa_addr)
            assert data == 0x11
            data = yield from read(pb_addr)
            assert data == 0x22
            now = yield from clk()
            print(f"Done at {now}")

    test.simulation(top, inspect.currentframe().f_code.co_name)

def test_reg2():
    class top(Module):
        def body(self):
            self.clk = Wire(logic)

            c1 = self.clk
            c2 = ~self.clk
            c3 = ~c2
            c4 = ~c3

            r00 = Reg(self.clk)
            r01 = Reg(c1)
            r02 = Reg(c2)
            r03 = Reg(c3)
            r04 = Reg(c4)

            with c1 as clk:
                r10 = Reg(self.clk)
                r11 = Reg(c1)
                r12 = Reg(c2)
                r13 = Reg(c3)
                r14 = Reg(c4)

            with c2 as clk:
                r20 = Reg(self.clk)
                r21 = Reg(c1)
                r22 = Reg(c2)
                r23 = Reg(c3)
                r24 = Reg(c4)

            with c3 as clk:
                r30 = Reg(self.clk)
                r31 = Reg(c1)
                r32 = Reg(c2)
                r33 = Reg(c3)
                r34 = Reg(c4)

            with c4 as clk:
                r40 = Reg(self.clk)
                r41 = Reg(c1)
                r42 = Reg(c2)
                r43 = Reg(c3)
                r44 = Reg(c4)

        def simulate(self):
            for i in range(10):
                self.clk = 0
                yield 10
                self.clk = 1
                yield 10

    test.simulation(top, inspect.currentframe().f_code.co_name)


if __name__ == "__main__":
    test_sim_update()
    #test_reg2()
