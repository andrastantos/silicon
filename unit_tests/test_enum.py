#!/usr/bin/python3
import sys
import os
from unit_tests.test_utils import skip_iverilog
sys.path.append(os.path.join(os.path.dirname(__file__),".."))

from typing import *

from silicon import *
from test_utils import *
import inspect

def test_enum1(mode = "rtl"):
    class E1(PyEnum):
        first=1
        second=2
        third=3

    class top(Module):
        in_a = Input(Enum(E1))
        out_a = Output(Enum(E1))

        def body(self):
            self.out_a = self.in_a

    class top_tb(top):
        def simulate(self):
            yield 10
            for e in E1:
                self.in_a <<= e
                yield 10
            self.in_a <<= None
            yield 10
            print("Done")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(top_tb, "test_enum1")

def test_enum_const():
    class E1(PyEnum):
        first=1
        second=2
        third=3

    class top(Module):
        in_a = Input(Enum(E1))
        out_a = Output(Enum(E1))

        def body(self):
            self.out_a = E1.first

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_enum_add(mode = "rtl"):
    class E1(PyEnum):
        first=1
        second=2
        third=3

    class top(Module):
        in_a = Input(Enum(E1))
        out_a = Output()

        def body(self):
            self.out_a = E1.first + self.in_a

    class top_tb(top):
        def simulate(self):
            yield 10
            for e in E1:
                self.in_a <<= e
                yield 10
            self.in_a <<= None
            yield 10
            print("Done")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(top_tb, "test_enum_add")

def test_enum_and1():
    class E1(PyEnum):
        zero=0
        first=1
        second=2
        third=3

    class top(Module):
        in_a = Input(Enum(E1))
        out_a = Output(Enum(E1))

        def body(self):
            self.out_a = E1.first & self.in_a

    with ExpectError(SyntaxErrorException):
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_enum_and2():
    class E1(PyEnum):
        first=1
        second=2
        third=3

    class top(Module):
        in_a = Input(Enum(E1))
        out_a = Output()

        def body(self):
            self.out_a = E1.first & self.in_a

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

@skip_iverilog
def test_enum_adapt():
    class E1(PyEnum):
        zero=0
        first=1
        second=2
        third=3

    class top(Module):
        in_a = Input(logic)
        out_a = Output(Enum(E1))

        def body(self):
            self.out_a = explicit_adapt(self.in_a, Enum(E1))

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


@skip_iverilog
def test_enum_adapt2(mode = "rtl"):
    class E1(PyEnum):
        zero=0
        first=1
        second=2
        third=3

    class top(Module):
        in_a = Input(Unsigned(5))
        out_a = Output(Enum(E1))

        def body(self):
            self.out_a = explicit_adapt(self.in_a, Enum(E1))

    class top_tb(top):
        def simulate(self):
            yield 10
            for e in range(4):
                self.in_a <<= e
                yield 10
            self.in_a <<= None
            yield 10
            print("Done")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(top_tb, "test_enum_adapt2")


def test_enum_adapt2_sim():
    test_enum_adapt2("sim")


if __name__ == "__main__":
    #test_enum1()
    #test_enum_const()
    test_enum_add()
    #test_enum_and1()
    #test_enum_and2()
    #test_enum_adapt()
    #test_enum_adapt2("sim")
