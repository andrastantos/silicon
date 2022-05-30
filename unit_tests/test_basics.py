#!pytest
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / ".."))
import silicon as si
import test_utils as t
import inspect
import pytest

# Some of the simplest tests

# 1. Simply instantiate a module. Not even any IO
#################################################
def test_empty_module():
    class top(si.Module):
        def body(self):
            pass

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)

# 2. A module with some I/O
#################################################
def test_module_with_io():
    class top(si.Module):
        input_port = si.Input(si.Signed(8))
        output_port = si.Output(si.Signed(8))
        def body(self):
            pass

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)

# 3. A module with output assigned to constant and input
#################################################
def test_module_with_assigned_io():
    class top(si.Module):
        input_port = si.Input(si.Signed(8))
        output1 = si.Output(si.Signed(8))
        output2 = si.Output(si.Signed(8))
        def body(self):
            self.output1 = self.input_port
            self.output2 = 0

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name, allow_new_attributes=True)


# 4. Testing pass-through of inlined modules
#################################################
def test_pass_through():
    class top(si.Module):
        out_a = si.Output(si.Signed(5))
        in_a = si.Input(si.Signed(1))
        in_b = si.Input(si.Signed(1))

        def body(self):
            self.out_a[1:0] = 0
            self.out_a[3:2] = 1
            self.out_a[4] = self.in_a & self.in_b

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_wire_names():
    class top(si.Module):
        out_a = si.Output(si.logic)
        out_b = si.Output(si.logic)
        out_aa = si.Output(si.logic)
        out_bb = si.Output(si.logic)
        in_a = si.Input(si.logic)
        in_b = si.Input(si.logic)

        def body(self):
            a = si.Wire(si.logic)
            self.aa = a
            self.bb = si.Wire(si.logic)
            b = self.bb
            self.out_a <<= a
            self.out_b <<= b
            self.out_aa <<= self.aa
            self.out_bb <<= self.bb
            a <<= self.in_a
            b <<= self.in_b

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_wire_array3():
    class top(si.Module):
        out_a = si.Output(si.Unsigned(length=8))
        in_a = si.Input(si.Unsigned(length=8))

        def body(self):
            bits = []
            for inp in self.in_a:
                bits.append(si.Wire())
                bits[-1] <<= inp
            for idx, bit in enumerate(bits):
                self.out_a[idx] = bit

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)


def test_slice_bind():
    class top(si.Module):
        out_a = si.Output(si.Unsigned(length=8))
        in_a = si.Input(si.Unsigned(length=8))

        def body(self):
            self.out_a[0] <<= self.in_a[0]
            self.out_a[7:1] <<= 1

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_module_decorator():
    @si.module(1)
    def function_as_module(a, b) -> si.Output:
        return a + b

    class Top(si.Module):
        out_a = si.Output(si.Signed(5))
        out_b = si.Output(si.Signed(5))
        out_c = si.Output(si.Signed(5))
        in_a = si.Input(si.Signed(1))
        in_b = si.Input(si.Signed(1))

        def body(self):
            self.out_a = function_as_module(self.in_a, self.in_b)
            self.out_b = function_as_module(self.in_a, self.in_b)
            self.out_c = function_as_module(self.in_a, 1)

    t.test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

def test_module_decorator1():
    @si.module(1)
    def function_as_module(a, b) -> si.Output:
        return a + b

    class Top(si.Module):
        out_a = si.Output(si.Signed(5))
        in_a = si.Input(si.Signed(3))
        in_b = si.Input(si.Signed(3))

        def body(self):
            self.out_a = function_as_module(self.in_a, self.in_b)

    t.test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

def test_double_port_assign():
    class and_gate(si.Module):
        in_a = si.Input(si.logic)
        in_b = si.Input(si.logic)
        out_a = si.Output(si.logic)

        def body(self) -> None:
            pass

    class top(si.Module):
        in_a = si.Input(si.logic)
        out_a = si.Output(si.logic)

        def body(self):
            A = and_gate()
            A(in_a = self.in_a)
            A.in_b = self.in_a
            self.out_a = A.out_a

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)


"""
# 4. Testing pass-through of inlined modules in loops
#################################################
def test_pass_through_loop():
    class top(si.Module):
        out_a = si.Output(si.Signed(5))
        in_a = si.Input(si.Signed(1))
        in_b = si.Input(si.Signed(1))

        def body(self):
            c[0] = self.in_a & self.in_b
            self.out_a[1:0] = 0
            self.out_a[3:2] = 1
            self.out_a[4] = self.in_a & self.in_b

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)
"""

"""
class FullAdder(si.Module):
    in_a = si.Input(si.logic)
    in_b = si.Input(si.logic)
    in_c = si.Input(si.logic)
    out_r = si.Output(si.logic)
    out_c = si.Output(si.logic)

    def body(self):
        self.out_r <<= self.in_a ^ self.in_b ^ self.in_c
        self.out_c <<= (self.in_a & self.in_b) | (self.in_b & self.in_c) | (self.in_c & self.in_a)

def test_full_adder():
    top = FullAdder()
    netlist = si.elaborate(top)
    rtl = si.StrStream()
    netlist.generate(netlist, si.SystemVerilog(rtl))
    print(rtl)
"""

def test_loop_finder(mode="rtl"):
    class Top(si.Module):
        clk = si.Input(si.logic)
        rst = si.Input(si.logic)

        def body(self):
            """
            Testing for diverging, then re-combining combinatorial
            graphs. These have non-directed loops in them, but
            still are DAGs, so the loop finder should not get triggered.
            """
            self.decode_fsm = si.FSM()

            self.decode_fsm.reset_value <<= 0
            self.decode_fsm.default_state <<= 0

            aaa = (self.decode_fsm.state == 0)
            ddd = (self.decode_fsm.state == 0)
            self.decode_fsm.add_transition(0, aaa, 1)
            self.decode_fsm.add_transition(0, ddd, 3)


    if mode == "rtl":
        t.test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)














if __name__ == "__main__":
    #test_module_decorator1()
    #test_module_decorator()
    #test_empty_module()
    #test_module_with_io()
    #test_module_with_assigned_io()
    test_pass_through()
    #test_wire_names()
    #test_wire_array3()
    #test_slice_bind()
    #test_double_port_assign()
    #test_full_adder()
    test_loop_finder("rtl")