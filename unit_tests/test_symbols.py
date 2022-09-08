#!/usr/bin/python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / ".."))

from typing import *

from silicon import *
from test_utils import *
import inspect

class and_gate(Module):
    in_a = Input(logic)
    in_b = Input(logic)
    out_a = Output(logic)
    def body(self):
        self.out_a <<= self.in_a & self.in_b

class or_gate(Module):
    in_a = Input(logic)
    in_b = Input(logic)
    out_a = Output(logic)
    def body(self):
        self.out_a <<= self.in_a | self.in_b

class xor_gate(Module):
    in_a = Input(logic)
    in_b = Input(logic)
    out_a = Output(logic)
    def body(self):
        self.out_a <<= self.in_a ^ self.in_b

class full_adder(Module):
    in_a = Input(logic)
    in_b = Input(logic)
    in_c = Input(logic)
    out_a = Output(logic)
    out_c = Output(logic)

    def body(self):
        self.out_a <<= xor_gate(self.in_a, xor_gate(self.in_b, self.in_c))
        self.out_c <<= or_gate(
            and_gate(self.in_a, self.in_b),
            or_gate(
                and_gate(self.in_a, self.in_c),
                and_gate(self.in_b, self.in_c)
            )
        )

def test_named_sub_modules():
    class top(Module):
        in_1 = Input(logic)
        in_2 = Input(logic)
        out_1 = Output(logic)

        def body(self):
            A = and_gate()
            A(in_a = self.in_1)
            A.in_b <<= self.in_2
            self.out_1 <<= A.out_a


    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


def test_sub_module_name_collision():
    class top(Module):
        in_1 = Input(logic)
        in_2 = Input(logic)
        out_1 = Output(logic)
        out_2 = Output(logic)

        def body(self):
            u = and_gate()
            self.out_1 <<= u(self.in_1, self.in_2)
            self.out_2 <<= or_gate(self.in_1, self.in_2)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_wire_sub_module_name_collision():
    class top(Module):
        in_1 = Input(logic)
        in_2 = Input(logic)
        out_1 = Output(logic)
        out_2 = Output(logic)

        def body(self):
            u = Wire(logic)
            u <<= and_gate(self.in_1, self.in_2)
            self.out_1 <<= u
            self.out_2 <<= or_gate(self.in_1, self.in_2)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


if __name__ == "__main__":
    test_named_sub_modules()
    #test_sub_module_name_collision()
    #test_wire_sub_module_name_collision()

