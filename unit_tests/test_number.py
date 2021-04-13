#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__),".."))

from typing import *

from silicon import *
from test_utils import *
import inspect

class and_gate(Module):
    in_a = Input(logic)
    in_b = Input(logic)
    out_a = Output(logic)
    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        ret_val = ""
        assert back_end.language == "SystemVerilog"
        ret_val += self.generate_module_header(back_end) + "\n"
        ret_val += back_end.indent("assign out_a = in_a & in_b;\n")
        ret_val += "endmodule\n\n\n"
        return ret_val

class or_gate(Module):
    in_a = Input(logic)
    in_b = Input(logic)
    out_a = Output(logic)
    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        ret_val = ""
        assert back_end.language == "SystemVerilog"
        ret_val += self.generate_module_header(back_end) + "\n"
        ret_val += back_end.indent("assign out_a = in_a | in_b;\n")
        ret_val += "endmodule\n\n\n"
        return ret_val

class xor_gate(Module):
    in_a = Input(logic)
    in_b = Input(logic)
    out_a = Output(logic)
    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        ret_val = ""
        assert back_end.language == "SystemVerilog"
        ret_val += self.generate_module_header(back_end) + "\n"
        ret_val += back_end.indent("assign out_a = in_a ^ in_b;\n")
        ret_val += "endmodule\n\n\n"
        return ret_val

class full_adder(Module):
    in_a = Input(logic)
    in_b = Input(logic)
    in_c = Input(logic)
    out_a = Output(logic)
    out_c = Output(logic)
    
    def body(self):
        self.out_a = xor_gate(self.in_a, xor_gate(self.in_b, self.in_c))
        self.out_c = or_gate(
            and_gate(self.in_a, self.in_b),
            or_gate(
                and_gate(self.in_a, self.in_c),
                and_gate(self.in_b, self.in_c)
            )
        )

def test_mix1():
    class top(Module):
        in_a = Input(Unsigned(length=5))
        in_b = Input(Unsigned(length=16))
        in_c = Input(Unsigned(length=16))
        out_num = Output(Unsigned(length=16))
        out_num_b = Output(Signed(length=16))
        out_a = Output(Unsigned(length=1))
        out_b = Output(Unsigned(length=11))
        out_c = Output(Unsigned(length=5))
        out_d = Output(Unsigned(length=11))

        def body(self):
            # Funny thing. This works:
            #   (a, b) = some_multi_output_gate()
            # This also works:
            #   bus = (a, b, c)
            # This stuff doesn't:
            #   (a, b) = (c, d, e)
            # But, this works too, provided all elements are broken out:
            #   (a, b) = bus
            # This again, is borken:
            #   (a, bus_a) = bus_b
            # But maybe it's an edge-case enough that it doesn't matter. We at least get a Python error for the broken cases.
            # We can also make a 'concat' and a 'split' module if we really want to to make single-line assignments like that work.
            a0 = self.in_a[0]
            #a0_alias1 = a0
            #a0_alias2 = a0
            b0 = self.in_b[0]
            c0 = and_gate(a0, b0)
            #in_a_alias = c0.get_parent_module().in_a
            self.out_num = self.in_b & self.in_c
            self.out_num_b = 31
            self.out_b[0] = c0
            self.out_b[4] = and_gate(self.in_a[3], self.in_a[4])
            self.out_b[3:1] = self.in_a[2:0]
            self.out_b[10:5] = 0
            self.out_c = concat(a0, b0, c0, c0, b0)
            # There's a strange artifact in the generation of this code. It outputs:
            #   assign out_d = {{7{1'bX}}, {in_a[4], in_b[0], u1_out}};
            # This is probably not a big deal, but maybe at some point we should optimize away the extra {} braces to improve readability.
            self.out_d[3:0] = concat(c0, b0, self.in_a[4])
            self.out_d[10:4] = 1

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_assign():
    class top(Module):
        uout1 = Output(Unsigned(length=16))
        sout1 = Output(Signed(length=16))
        uout2 = Output(Unsigned(length=16))
        sout2 = Output(Signed(length=16))
        in1 = Input(logic)
        in2 = Input(logic)
        out1 = Output(logic)

        def body(self):
            self.out1 = self.in1
            self.uout1 = 42
            self.sout1 = 43
            with ExpectError(SyntaxErrorException):
                self.uout2 = -44
            self.sout2 = -45

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_concatenate():
    class top(Module):
        uout1 = Output(Unsigned(length=16))
        sout1 = Output(Signed(length=16))
        uin1 = Input(Unsigned(length=4))
        uin2 = Input(Unsigned(length=4))
        sin1 = Input(Signed(length=4))
        sin2 = Input(Signed(length=4))

        def body(self):
            self.uout1 = concat(self.uin1, self.uin2)
            self.sout1 = concat(self.sin1, self.uin1)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_binary_ops():
    class top(Module):
        uout1 = Output(Unsigned(length=4))
        uout2 = Output(Unsigned(length=4))
        uout3 = Output(Unsigned(length=4))
        uout4 = Output(Unsigned(length=4))
        uout5 = Output(Unsigned(length=4))
        uout6 = Output(Unsigned(length=4))
        uout7 = Output(Unsigned(length=4))
        uout8 = Output(Unsigned(length=4))
        uout9 = Output(Unsigned(length=4))
        uout10 = Output(Unsigned(length=4))
        uout11 = Output(Unsigned(length=4))
        uout12 = Output(Unsigned(length=4))
        sout1 = Output(Signed(length=4))
        sout4 = Output(Signed(length=4))
        sout5 = Output(Signed(length=4))
        uin1 = Input(Unsigned(length=4))
        uin2 = Input(Unsigned(length=4))
        uin3 = Input(Unsigned(length=1))
        uin4 = Input(Unsigned(length=3))
        uin5 = Input(Unsigned(length=4))
        sin1 = Input(Signed(length=4))
        sin2 = Input(Signed(length=4))
        sin3 = Input(Signed(length=2))
        sout2 = Output(Signed(length=5))
        sout3 = Output(Signed(length=5))
        lt_out = Output(Unsigned(length=1))
        le_out = Output(Unsigned(length=1))
        eq_out = Output(Unsigned(length=1))
        ne_out = Output(Unsigned(length=1))
        gt_out = Output(Unsigned(length=1))
        ge_out = Output(Unsigned(length=1))
        slsh_out = Output(Signed(length=4+2<<4))
        ulsh_out = Output(Unsigned(length=4+2<<4))
        srsh_out = Output(Signed(length=4+2<<4))
        ursh_out = Output(Unsigned(length=4+2<<4))

        def body(self):
            self.uout1 = self.uin1 & self.uin2
            self.sout1 = self.sin1 & self.sin1
            self.uout2 = self.uin1 & self.uin2 & self.uin3
            self.uout3 = self.uin1 & self.uin2 | self.uin1 & self.uin3
            self.uout4 = self.uin1 | self.uin2 & self.uin3 | self.uin4
            self.sout4 = (self.sin1 & self.sin3) | self.sin1
            self.sout5 = (self.sin1 | self.sin3) & self.sin1
            self.uout7 = self.uin1 & (self.uin2 | self.uin3)
            self.uout8 = self.uin1 | (self.uin2 & self.uin3)
            for i in range(0,4):
                self.uout9[i] = self.uin1[i] & (self.uin2[3-i] | self.uin5[i])
                self.uout10[i] = (self.uin1 & (self.uin2 | self.uin5))[i]
                self.uout11[3-i] = (self.uin1 & (self.uin2 | self.uin5))[i]
                #if i >= 2:
                    #self.uout10[i] = (self.uin1 & (self.uin2 | self.sin1))[i]
                    #self.uout11[3-i] = (self.uin1 & (self.uin2 | self.sin1))[i]
                    #self.uout12[(3-i)*2] = (self.uin1 & (self.uin2 | self.sin1))[i]
            self.sout2 = self.sin1 + self.sin2
            self.sout3 = self.sin1 - self.sin2
            self.lt_out = self.sin1 < self.sin2
            self.le_out = self.sin1 <= self.sin2
            self.eq_out = self.sin1 == self.sin2
            self.ne_out = self.sin1 != self.sin2
            self.gt_out = self.sin1 > self.sin2
            self.ge_out = self.sin1 >= self.sin2
            self.slsh_out = self.sin1 << self.uin1
            self.ulsh_out = self.uin1 << self.uin1
            self.srsh_out = self.sin1 >> self.uin1
            self.ursh_out = self.uin1 >> self.uin1
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_closure():
    class top(Module):
        uout11 = Output(Unsigned(length=1))
        uin1 = Input(Unsigned(length=1))
        uin2 = Input(Unsigned(length=1))

        def body(self):
            self.uout11[0] = (self.uin1 & self.uin2)[0]
            
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_closure1():
    class top(Module):
        uout11 = Output(Unsigned(length=1))
        uin1 = Input(Unsigned(length=1))
        uin2 = Input(Unsigned(length=1))

        def body(self):
            self.uout11 = (self.uin1 & self.uin2)[0]
            
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_closure2():
    class top(Module):
        uout11 = Output(Unsigned(length=1))
        uin1 = Input(Unsigned(length=1))
        uin2 = Input(Unsigned(length=1))

        def body(self):
            self.uout11[0] = (self.uin1 | self.uin2)[0]
            
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_slices():
    class top(Module):
        uout1 = Output(Unsigned(length=1))
        uout2 = Output(Unsigned(length=2))
        sout1 = Output(Signed(length=8))
        sout4 = Output(Signed(length=8))
        uin1 = Input(Unsigned(length=1))
        uin2 = Input(Unsigned(length=2))
        uin3 = Input(Unsigned(length=3))
        uin4 = Input(Unsigned(length=4))
        uin5 = Input(Unsigned(length=5))
        sin1 = Input(Signed(length=1))
        sin2 = Input(Signed(length=2))
        sin3 = Input(Signed(length=3))
        sin4 = Input(Signed(length=4))
        sin5 = Input(Signed(length=5))

        def body(self):
            self.uout1[0] = self.uin1
            self.uout2[1] = self.uin1
            self.uout2[0] = self.uin1
            self.sout1 = self.sin1[0]

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


def test_slice_new():
    class top(Module):
        uout1 = Output(Unsigned(length=2))
        uout2 = Output(Unsigned(length=2))
        uin1 = Input(Unsigned(length=2))

        def body(self):
            self.uout1[0] <<= self.uin1[0]
            self.uout1[1] = self.uin1[1]
            #x = self.uout2[0]
            #x <<= self.uin1[0]
            #self.uout2[1] = self.uin1[1]

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_slice_with():
    class top(Module):
        uout1 = Output(logic)
        uout2 = Output(logic)
        uin1 = Input(Unsigned(length=2))

        def body(self):
            with self.uin1[0] as x:
                self.uout2 = x
            self.uout1 = self.uin1[1]

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_slice_slice():
    class top(Module):
        uout1 = Output(logic)
        uout2 = Output(Unsigned(length=5))
        uout3 = Output(Unsigned(length=5))
        uout4 = Output(Unsigned(length=5))
        uin1 = Input(Unsigned(length=10))
        uin2 = Input(logic)

        def body(self):
            self.uout1 = self.uin1[5:2][1]
            self.uout2 = self.uin1[9:3][6:1][5:1]
            self.uout3[4:1][1] = self.uin1[0]
            self.uout3[4:1][3:2] <<= self.uin2
            self.uout3[1:0] = self.uin1[2]

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_partial_assign():
    class top(Module):
        uout = Output(Unsigned(length=5))
        uin = Input(Unsigned(length=10))

        def body(self):
            self.uout[1] = self.uin[0]
            self.uout[0] = self.uin[1]
            #self.uout3[4:1][3:2] <<= self.uin1[1]
            #self.uout3[1:0] = self.uin1[2]

    with ExpectError(SyntaxErrorException):
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_decorator_slice():
    @module(1)
    def return_slice(a) -> Output:
        return a[0]
    @module(1)
    def get_slice(a, b) -> Output:
        return a+b

    class Top(Module):
        out_a = Output(Unsigned(5))
        out_b = Output(Unsigned(5))
        in_a = Input(Unsigned(3))
        in_b = Input(Unsigned(3))

        def body(self):
            self.out_a = return_slice(self.in_a)
            self.out_b = get_slice(self.in_a[2:0], self.in_b[1])

    test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

def test_slice_sim():
    # TODO: test simulation, where 'simulate' function does slice assignment using = and <<=
    # TODO: test sim where we yield a slice (that should maybe be an error??)
    pass

def test_slice_as_return():

    class Top(Module):
        out_a = Output(Unsigned(5))
        out_b = Output(Unsigned(8))
        in_a = Input(Unsigned(4))
        in_b = Input(Unsigned(4))
        in_c = Input(logic)

        def body(self):
            def daa_correct_digit(digit, sub_not_add):
                new_val = Select(sub_not_add, digit + 1, digit - 1)
                return new_val[4], new_val[3:0]

            daa_step_1_carry, daa_digit_1 = daa_correct_digit(self.in_a, self.in_c)
            daa_step_2_carry, daa_digit_2 = daa_correct_digit(self.in_a, self.in_c)
            daa_res = concat(daa_digit_2, daa_digit_1)
            self.out_a = self.in_b + daa_step_1_carry + daa_step_2_carry
            self.out_b = daa_res

    test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

def test_local_slice():

    class Top(Module):
        out_a = Output(Unsigned(5))
        in_c = Input(logic)

        def body(self):
            x = self.out_a[3:0]
            x <<= self.in_c
            self.out_a[4] = 1

    test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

def test_wire_to_wire_loop():

    class Top(Module):
        out_a = Output(Unsigned(5))
        in_c = Input(Unsigned(4))

        def body(self):
            y = Wire(Unsigned(4))
            y[2:0] <<= self.in_c[2:0]
            y[3] <<= y[3]
            self.out_a <<= y

    with ExpectError(SyntaxErrorException):
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

def test_precedence():
    class Top(Module):
        in1 = Input(Unsigned(8))
        in2 = Input(Unsigned(8))
        alpha = Input(Unsigned(8))
        outp = Output(Unsigned(8))
        
        def body(self):
            #pix1 = self.in1 * self.alpha
            pix2 = self.in2 * (255-self.alpha)
            #self.outp = (pix1 + pix2)[15:8]
            self.outp = pix2[15:8]

    test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

if __name__ == "__main__":
    #test_mix1()
    #test_binary_ops()
    #test_closure()
    #test_closure1()
    #test_closure2()
    test_slices()
    #test_assign()
    #test_concatenate()
    #test_slice_new()
    #test_slice_with()
    #test_slice_slice()
    #test_decorator_slice()
    #test_slice_as_return()
    #test_local_slice()
    #test_wire_to_wire_loop()
    #test_partial_assign()
    #test_precedence()
    pass

'''
class S(object):
    def __set__(self, instance, value):
        print(f"Set called with {value} on instance {instance}")
    def __get__(self, instance, owner):
        print(f"Get called with {owner} on instance {instance}")
        return 42

class B(object):
    ss = S() # Descriptors need to be set on the *class*, not on the instance
    def __init__(self):
        self.s = S() # This doesn't do anything special

b = B()
b.ss = 32
print(b.ss)


import random

class Die(object):
    def __init__(self, sides=6):
        self.sides = sides

    def __get__(self, instance, owner):
        return int(random.random() * self.sides) + 1


class Game(object):
    d6 = Die()
    d10 = Die(sides=10)
    d20 = Die(sides=20)

print(Game.d6)
print(Game.d6)
print(Game.d6)
'''