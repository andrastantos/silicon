#!pytest
import sys
from pathlib import Path

from silicon.utils import VerbosityLevels
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
            self.output1 <<= self.input_port
            self.output2 <<= 0

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name, allow_new_attributes=True)


# 4. Testing pass-through of inlined modules
#################################################
def test_pass_through():
    class top(si.Module):
        out_a = si.Output(si.Signed(5))
        in_a = si.Input(si.Signed(1))
        in_b = si.Input(si.Signed(1))

        def body(self):
            self.out_a[1:0] <<= 0
            self.out_a[3:2] <<= 1
            self.out_a[4] <<= self.in_a & self.in_b

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_multiple_wire_names():
    class top(si.Module):
        top_port = si.Input(si.logic)
        top_out = si.Output(si.logic)

        def body(self):
            a = self.top_port
            aa = a
            self.top_out <<= aa

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
                self.out_a[idx] <<= bit


    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_wire_array2():
    class top(si.Module):
        out_a = si.Output(si.Unsigned(length=8))
        in_a = si.Input(si.Unsigned(length=8))

        def body(self):
            bits = []
            but = si.Wire()
            for inp in self.in_a:
                bits.append(si.Wire())
                bits[-1] <<= inp
            for idx, bit in enumerate(bits):
                self.out_a[idx] <<= bit
            but <<= inp


    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_scoped_bind():
    class top(si.Module):
        out_a = si.Output(si.Unsigned(8))
        out_b = si.Output(si.Unsigned(8))
        out_c = si.Output(si.Unsigned(8))
        out_d = si.Output(si.Unsigned(8))
        out_e = si.Output(si.Unsigned(8))
        out_f = si.Output(si.Unsigned(8))
        out_g = si.Output(si.Unsigned(8))
        out_h = si.Output(si.Unsigned(8))
        out_i = si.Output(si.Unsigned(8))
        in_a = si.Input(si.Unsigned(8))
        in_b = si.Input(si.Unsigned(8))
        in_c = si.Input(si.Unsigned(8))
        in_d = si.Input(si.Unsigned(8))

        def body(self):
            a = self.in_a
            with self.in_a as a:
                self.out_a <<= a
            self.out_b <<= a
            with self.in_c as a:
                self.out_c <<= a
                with self.in_b as a:
                    self.out_e <<= a
                self.out_f <<= a
            with self.in_d as a:
                with self.in_d as b:
                    self.out_g <<= b
                self.out_h <<= a
                with t.ExpectError():
                    self.out_i <<= b # should be an error
            self.out_d <<= a

    si.set_verbosity_level(VerbosityLevels.instantiation)
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
        out_d = si.Output(si.Signed(5))
        out_e = si.Output(si.Signed(5))
        out_f = si.Output(si.Signed(5))
        in_a = si.Input(si.Signed(1))
        in_b = si.Input(si.Signed(1))

        def body(self):
            self.out_a <<= function_as_module(a=self.in_a, b=self.in_b)
            self.out_b <<= function_as_module(self.in_a, b=self.in_b)
            self.out_c <<= function_as_module(self.in_a, self.in_b)
            self.out_d <<= function_as_module(1, self.in_b)
            self.out_e <<= function_as_module(self.in_a, 2)
            self.out_f <<= function_as_module(1, 2)

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
            self.out_a <<= function_as_module(self.in_a, self.in_b)

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
            A.in_b <<= self.in_a
            self.out_a <<= A.out_a

    t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_comb_loop_slice():
    class top(si.Module):
        in_a = si.Input(si.Unsigned(2))
        out_a = si.Output(si.Unsigned(2))

        def body(self):
            self.out_a[0] <<= 1
            self.out_a[1] <<= self.out_a[0] & self.in_a[1] # This is marked as a combinational loop even though it's technically not.

    with t.ExpectError(si.SyntaxErrorException):
        t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_invalid_slice():
    class top(si.Module):
        in_a = si.Input(si.Unsigned(2))
        out_a = si.Output(si.Unsigned(2))

        def body(self):
            self.in_a[0] <<= 1 # This is an invalid binding of an input port (slice)

    with t.ExpectError(si.SyntaxErrorException):
        t.test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_output_slice():
    class top(si.Module):
        in_a = si.Input(si.Unsigned(2))
        out_a = si.Output(si.Unsigned(2))
        clk = si.Input(si.logic)

        def body(self):
            self.out_a[0] <<= si.Reg(self.out_a[1] & self.in_a[0]) # This is an invalid binding of an input port (slice)
            self.out_a[1] <<= self.in_a[1]

    #with t.ExpectError(si.SyntaxErrorException):
    if True:
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
        clk = si.ClkPort()
        rst = si.RstPort()

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





def test_default_port(mode="rtl"):
    class Sub(si.Module):
        a_sub = si.Input(si.Unsigned(7), default_value = 123)
        o_sub = si.Output(si.Unsigned(8))

        def body(self):
            self.o_sub <<= self.a_sub
    class Top(si.Module):
        a_top = si.Input(si.Unsigned(7), default_value = 42) # At the top level, optional ports must stay in the interface
        o_top = si.Output(si.Unsigned(7))
        o2_top = si.Output(si.Unsigned(8))

        def body(self):
            self.o_top <<= self.a_top
            self.o2_top <<= Sub()()

    if mode == "rtl":
        t.test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)




def test_mixed_sources(mode="rtl"):
    class Top(si.Module):
        a = si.Input(si.Unsigned(8))
        o = si.Output(si.Unsigned(8))

        def body(self):
            self.o <<= self.a
            self.o[0] <<= self.a[2]
            self.o[7:1] <<= self.a[7:1]

    si.set_verbosity_level(VerbosityLevels.instantiation)
    with t.ExpectError(si.SyntaxErrorException):
        if mode == "rtl":
            t.test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
        else:
            t.test.simulation(Top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)

def test_rhs_slice(mode="rtl"):
    class Top(si.Module):
        a = si.Input(si.Unsigned(8))
        o = si.Output(si.Unsigned(8))
        p = si.Output(si.Unsigned(8))
        q = si.Output(si.Unsigned(8))

        def body(self):
            self.o <<= self.a[2]
            self.p <<= self.a[5:0][2]
            self.q <<= self.a[7:0][6:0][5:0]

    si.set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)


def test_lhs_slice(mode="rtl"):
    class Top(si.Module):
        a = si.Input(si.Unsigned(2))
        b = si.Input(si.Unsigned(3))
        c = si.Input(si.Unsigned(4))
        d = si.Input(si.Unsigned(5))
        o = si.Output(si.Unsigned(8))
        #p = si.Output(si.Unsigned(8))
        #q = si.Output(si.Unsigned(8))
        #r = si.Output(si.Unsigned(8))

        def body(self):
            self.o[3:0][2:0] <<= self.a
            self.o[3:0][3] <<= self.a[0]
            self.o[6:4] <<= self.b
            self.o[7] <<= self.c[3]

    si.set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)


def test_external_loopback(mode="rtl"):
    class Inner(si.Module):
        inner_in = si.Input(si.logic)
        inner_out = si.Output(si.logic)

        def body(self):
            self.inner_out <<= 1

    class Outer(si.Module):

        def body(self):
            loopback = si.Wire(si.logic)

            loopback <<= Inner(loopback)

    si.set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Outer, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Outer, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)



def test_internal_loopback(mode="rtl"):
    class Inner(si.Module):
        inner_in = si.Input(si.logic)
        inner_out = si.Output(si.logic)

        def body(self):
            self.inner_out <<= self.inner_in

    class Outer(si.Module):
        outer_in = si.Input(si.logic)
        outer_out = si.Output(si.logic)

        def body(self):
            self.outer_out <<= Inner(self.outer_in)

    si.set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Outer, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Outer, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)



#
#    +-----------------------------------------+
#    |                OUTER                    |
#    |                                         |
#    |   +-----------------------------+       |
#    |   |                             |       |
#    |   |     +------------------+    |       |
#    |   |     |                  |    |       |
#    |   |     |                  |    |       |
#    | +-\/----/\-+           +---\/---/\---+  |
#    | |          |           |   |    |    |  |
#    | |          |           |   +----+    |  |
#    | |          |           |             |  |
#    | |  INNER1  |           |    INNER2   |  |
#    | +----------+           +-------------+  |
#    |                                         |
#    +-----------------------------------------+
#

def test_complex_loopback(mode="rtl"):
    class Inner2(si.Module):
        inner2_in = si.Input(si.logic)
        inner2_out = si.Output(si.logic)

        def body(self):
            self.inner2_out <<= self.inner2_in
    class Inner1(si.Module):
        inner1_in = si.Input(si.logic)
        inner1_out = si.Output(si.logic)

        def body(self):
            pass


    class Outer(si.Module):
        def body(self):
            inner1 = Inner1()
            inner2 = Inner2()
            inner1.inner1_in <<= inner2.inner2_out
            inner2.inner2_in <<= inner1.inner1_out

    si.set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Outer, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Outer, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)



def test_multiple_outputs(mode="rtl"):
    class Inner2(si.Module):
        inner2_out = si.Output(si.logic)

        def body(self):
            self.inner2_out <<= 1
    class Inner1(si.Module):
        inner1_in = si.Input(si.logic)
        inner1_out1 = si.Output(si.logic)
        inner1_out2 = si.Output(si.logic)

        def body(self):
            inner2 = Inner2()

            self.inner1_out1 <<= inner2.inner2_out
            self.inner1_out2 <<= inner2.inner2_out

    class Outer(si.Module):
        def body(self):
            wire1 = si.Wire(si.logic)
            wire2 = si.Wire(si.logic)
            inner1 = Inner1()
            wire1 <<= inner1.inner1_out1
            wire2 <<= inner1.inner1_out2

    si.set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Outer, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Outer, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)




def test_multiple_outputs_if(mode="rtl"):
    class IF(si.Interface):
        n1 = si.logic
        n2 = si.logic
        r1 = si.Reverse(si.logic)
        r2 = si.Reverse(si.logic)

    class Inner2(si.Module):
        inner2_out = si.Output(IF)

        def body(self):
            self.inner2_out.n1 <<= 1
            self.inner2_out.n2 <<= 1
    class Inner1(si.Module):
        inner1_in = si.Input(IF)
        inner1_out1 = si.Output(IF)
        inner1_out2 = si.Output(IF)

        def body(self):
            inner2 = Inner2()

            self.inner1_out1 <<= inner2.inner2_out
            self.inner1_out2 <<= inner2.inner2_out

    class Outer(si.Module):
        def body(self):
            wire1 = si.Wire(IF)
            wire2 = si.Wire(IF)
            inner1 = Inner1()
            wire1 <<= inner1.inner1_out1
            wire2 <<= inner1.inner1_out2

    si.set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Outer, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Outer, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)


def test_multiple_outputs_if_rev_member(mode="rtl"):
    class IF(si.Interface):
        n = si.logic
        r = si.Reverse(si.logic)

    class Inner2(si.Module):
        inner2_in = si.Input(IF)

        def body(self):
            self.inner2_in.r <<= 1
    class Inner1(si.Module):
        inner1_in1 = si.Input(IF)
        inner1_in2 = si.Input(IF)

        def body(self):
            inner2 = Inner2()

            self.inner1_in1.r <<= inner2.inner2_in.r
            self.inner1_in2.r <<= inner2.inner2_in.r

    class Outer(si.Module):
        def body(self):
            wire1 = si.Wire(IF)
            wire2 = si.Wire(IF)
            inner1 = Inner1()
            inner1.inner1_in1 <<= wire1
            inner1.inner1_in2 <<= wire2

    si.set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Outer, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Outer, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)


def test_multiple_outputs_if_rev_member2(mode="rtl"):
    class Bus(si.Interface):
        data_out        = si.Reverse(si.Unsigned(32))

    class Consumer1(si.Module):
        bus_if = si.Output(Bus)

        def body(self): pass

    class Consumer2(si.Module):
        bus_if = si.Output(Bus)

        def body(self): pass

    class Procuder(si.Module):
        fetch = si.Input(Bus)
        mem = si.Input(Bus)

        def body(self):
            data_out        = si.Wire(si.Unsigned(32))

            self.mem.data_out <<= data_out
            self.fetch.data_out <<= data_out

            data_out <<= 1

    class Top(si.Module):
        def body(self):
            # Connecting tissue
            c1bus = si.Wire(Bus)
            c2bus = si.Wire(Bus)

            producer = Procuder()
            consumer1 = Consumer1()
            consumer2 = Consumer2()

            producer.fetch <<= c1bus
            producer.mem <<= c2bus

            c1bus <<= consumer1.bus_if
            c2bus <<= consumer2.bus_if

    si.set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)


def test_multiple_outputs_if_member(mode="rtl"):
    class OutIf1(si.Interface):
        out_if1_member = si.logic

    class InIf(si.Interface):
        in_if_member = si.logic

    class OutIf2(si.Interface):
        out_if2_member = si.logic


    class Consumer(si.Module):
        consumer_in = si.Input(InIf)
        consumer_out1 = si.Output(OutIf1)
        consumer_out2 = si.Output(OutIf2)

        def body(self):
            self.consumer_out1.out_if1_member <<= self.consumer_in.in_if_member
            self.consumer_out2.out_if2_member <<= self.consumer_in.in_if_member

    class Producer(si.Module):
        in_if = si.Output(InIf)

        def body(self):
            self.in_if.in_if_member <<= 1

    class Top(si.Module):
        def body(self):
            # Connecting tissue
            mem_to_bus = si.Wire(OutIf1)
            in_if = si.Wire(InIf)
            out_if2 = si.Wire(OutIf2)

            producer = Producer()
            consumer = Consumer()

            in_if <<= producer.in_if

            consumer.consumer_in <<= in_if
            mem_to_bus <<= consumer.consumer_out1
            out_if2 <<= consumer.consumer_out2

    si.set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)


def test_named_local_output(mode="rtl"):
    class Top(si.Module):
        top_in1 = si.Input(si.logic)
        top_in2 = si.Input(si.logic)
        top_out = si.Output()
        def body(self):
            xxx = self.top_in1 & self.top_in2
            self.top_out <<= xxx

    si.set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)


def test_named_local_output2(mode="rtl"):
    class Top(si.Module):
        top_in1 = si.Input(si.logic)
        top_in2 = si.Input(si.logic)
        top_out = si.Output()
        def body(self):
            xxx = si.Wire()
            xxx <<= self.top_in1 & self.top_in2
            yyy = xxx
            self.top_out <<= yyy

    si.set_verbosity_level(VerbosityLevels.instantiation)
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
    #test_pass_through()
    #test_multiple_wire_names()
    #test_wire_names()
    #test_wire_array3()
    #test_wire_array2()
    #test_slice_bind()
    #test_double_port_assign()
    #test_full_adder()
    #test_loop_finder("rtl")
    #test_rhs_slice("rtl")
    #test_lhs_slice("rtl")
    #test_scoped_bind()
    #test_comb_loop_slice()
    #test_invalid_slice()
    #test_output_slice()
    #test_mixed_sources()
    #test_default_port()
    #test_external_loopback()
    #test_internal_loopback()
    #test_complex_loopback()
    #test_named_local_output()
    #test_named_local_output2()
    #test_multiple_outputs()
    #test_multiple_outputs_if()
    #test_multiple_outputs_if_rev_member()
    #test_multiple_outputs_if_rev_member2()
    test_multiple_outputs_if_member()