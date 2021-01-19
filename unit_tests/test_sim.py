#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__),".."))

from typing import *

from silicon import *
from test_utils import *
import inspect

def test_sim_gates():
    class top(Module):
        in_1 = Input(logic)
        in_2 = Input(logic)
        out_and = Output(logic)
        out_or = Output(logic)
        out_xor = Output(logic)

        def body(self):
            #A = and_gate()
            #self.out_1 = A.out
            #A.in_a = self.in_1
            #A.in_b = self.in_2
            self.out_and = self.in_1 & self.in_2
            self.out_or = self.in_1 | self.in_2
            self.out_xor = self.in_1 ^ self.in_2
        
        def simulate(self) -> TSimEvent:
            print("Simulation started")
            now = yield 10
            print(f"now: {now}")
            self.in_1 = 0
            self.in_2 = 0
            yield 10
            self.in_1 = 1
            self.in_2 = 0
            yield 10
            self.in_1 = 0
            self.in_2 = 1
            yield 10
            self.in_1 = 1
            self.in_2 = 1
            yield 10
            self.in_1 = None
            self.in_2 = None
            now = yield 10
            print(f"Done at {now}")

    test.simulation(top, inspect.currentframe().f_code.co_name)

def test_sim_select():
    class top(Module):
        def body(self):
            self.a = Wire(Unsigned(10))
            self.b = Wire(Unsigned(5))
            self.c = Wire(Unsigned(1))
            self.selectw = Wire(Unsigned(4))
            self.select_one_hot = Wire(Unsigned(4))
            self.select1 = Select(selector_port = self.selectw & 3, value_0 = self.a, value_1 = self.b, value_2 = self.c)
            self.select2 = SelectFirst(selector_0 = self.selectw[0], value_0 = self.a, selector_1 = self.selectw[1], value_1 = self.b, selector_2 = self.selectw[2], value_2 = self.c)
            self.select3 = SelectOne(selector_0 = self.select_one_hot[0], value_0 = self.a, selector_1 = self.select_one_hot[1], value_1 = self.b, selector_2 = self.select_one_hot[2], value_2 = self.c)
        
        def simulate(self) -> TSimEvent:
            print("Simulation started")
            self.a = 3
            self.b = 2
            self.c = 1
            for sel_val in range(15):
                sel_one_val = (1 << sel_val) & 15
                self.selectw = sel_val
                self.select_one_hot = sel_one_val
                yield 10

                if sel_val & 3 == 0:
                    assert self.select1.sim_value == self.a.sim_value
                elif sel_val & 3 == 1:
                    assert self.select1.sim_value == self.b.sim_value
                elif sel_val & 3 == 2:
                    assert self.select1.sim_value == self.c.sim_value
                else:
                    assert self.select1.sim_value is None

                if sel_val & 1 != 0:
                    assert self.select2.sim_value == self.a.sim_value
                elif sel_val & 2 != 0:
                    assert self.select2.sim_value == self.b.sim_value
                elif sel_val & 4 != 0:
                    assert self.select2.sim_value == self.c.sim_value
                else:
                    assert self.select2.sim_value is None

                if sel_one_val & 1 != 0:
                    assert self.select3.sim_value == self.a.sim_value
                elif sel_one_val & 2 != 0:
                    assert self.select3.sim_value == self.b.sim_value
                elif sel_one_val & 4 != 0:
                    assert self.select3.sim_value == self.c.sim_value
                else:
                    assert self.select3.sim_value is None
            print("Done")
    test.simulation(top, inspect.currentframe().f_code.co_name)

def test_sim_counter():
    class top(Module):

        def body(self):
            self.clock = Wire(logic)
            self.reset = Wire(logic)
            self.count = Wire(Unsigned(4))

            self.count = Reg((self.count + 1)[3:0])
        
        def simulate(self) -> TSimEvent:
            print("Simulation started")
            now = yield 10
            print(f"now: {now}")
            self.clock = 0
            self.reset = 1
            expected_count = 0
            for i in range(5):
                self.clock = 0
                now = yield 10
                print(f"now: {now}")
                self.clock = 1
                now = yield 10
                print(f"now: {now}")
            self.reset = 0
            print(f"now: {now} --------")
            for i in range(50):
                self.clock = 0
                now = yield 10
                print(f"now: {now}")
                assert self.count.sim_value == expected_count
                expected_count = (expected_count + 1) & 15
                self.clock = 1
                now = yield 10
                print(f"now: {now}")
            print(f"Done at {now}")

    test.simulation(top, "test_sim_counter")

def test_sim_concat():
    class top(Module):
        def body(self):
            self.uin1 = Wire(Unsigned(4))
            self.uin2 = Wire(Unsigned(4))
            self.uin3 = Wire(Unsigned(4))
            self.sin1 = Wire(Signed(4))
            self.out1 = Wire()
            self.out2 = Wire()
            self.out3 = Wire()

            self.out1 = [self.uin1, self.uin2]
            self.out2 = [self.sin1, self.uin1, self.uin2]
            self.out3 = concat(self.uin1, self.uin2, self.uin3)

        def simulate(self) -> TSimEvent:
            print("Simulation started")
            self.uin1 = 1
            self.uin2 = 2
            self.uin3 = "4'h3"
            self.sin1 = -1
            now = yield 10
            assert self.out1.sim_value == 0x12
            assert self.out2.sim_value == -238
            assert self.out3.sim_value == 0x123
            print("Done")
            pass

    test.simulation(top, inspect.currentframe().f_code.co_name)

if __name__ == "__main__":
    test_sim_gates()
    test_sim_counter()
    test_sim_select()
    test_sim_concat()

"""
An idea from PyRTL: use <<= as the 'bind' operator. Could re-use the same for simulation assignment, though that's ugly. (not that the current hack isn't either)

Alternatives:
    PyRTL - https://ucsbarchlab.github.io/PyRTL/
    pyverilog - https://pypi.org/project/pyverilog/ <-- actually, no, this is a Verilog parser and co. in Python.
    pyMTL - https://github.com/cornell-brg/pymtl
    myHDL - http://www.myhdl.org/

    All of them seem to take the road of trying to understand and convert python to RTL as opposed to 'describe' RTL in python.
"""