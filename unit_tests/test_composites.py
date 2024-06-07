#!/usr/bin/python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / ".."))

from typing import *

from silicon import *
from test_utils import *

import inspect

class Pixel(Struct):
    r = Unsigned(8)
    g = Unsigned(8)
    b = Unsigned(8)

def test_select_struct():
    class top(Module):
        out_port = Output(Pixel)
        in1 = Input(Pixel)
        in2 = Input(Pixel)
        in3 = Input(Pixel)
        in4 = Input(Pixel)
        sel_in = Input(Unsigned(2))

        def body(self):
            self.out_port <<= Select(self.sel_in, self.in1, self.in2, self.in3, self.in4)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_select_one_struct():
    class top(Module):
        out_port = Output(Pixel)
        in1 = Input(Pixel)
        in2 = Input(Pixel)
        in3 = Input(Pixel)
        in4 = Input(Pixel)
        sel_in = Input(Unsigned(4))

        def body(self):
            self.out_port <<= SelectOne(self.sel_in[0], self.in1, self.sel_in[1], self.in2, self.sel_in[2], self.in3, self.sel_in[3], self.in4)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_select_one_struct_default():
    class top(Module):
        out_port = Output(Pixel)
        in1 = Input(Pixel)
        in2 = Input(Pixel)
        in3 = Input(Pixel)
        in4 = Input(Pixel)
        sel_in = Input(Unsigned(4))

        def body(self):
            self.out_port <<= SelectOne(self.sel_in[0], self.in1, self.sel_in[1], self.in2, self.sel_in[2], self.in3, self.sel_in[3], self.in4, default_port=self.in2)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_select_first_struct(mode: str = "rtl"):
    class top(Module):
        out_port = Output(Pixel)
        in1 = Input(Pixel)
        in2 = Input(Pixel)
        in3 = Input(Pixel)
        in4 = Input(Pixel)
        sel_in = Input(Unsigned(4))

        def body(self):
            self.out_port <<= SelectFirst(self.sel_in[0], self.in1, self.sel_in[1], self.in2, self.sel_in[2], self.in3, self.sel_in[3], self.in4)
        def simulate(self):
            self.in1.r <<= 11
            self.in1.g <<= 12
            self.in1.b <<= 13
            self.in2.r <<= 21
            self.in2.g <<= 22
            self.in2.b <<= 23
            self.in3.r <<= 31
            self.in3.g <<= 32
            self.in3.b <<= 33
            self.in4.r <<= 41
            self.in4.g <<= 42
            self.in4.b <<= 43
            yield 10
            for self.sel_in in range(16):
                yield 10
            print("Done")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(top, "test_select_first_struct")

@pytest.mark.skip(reason="This is a test for something that only the new Composite infrastructure can handle well")
def test_type_propagation():
    class top(Module):
        in1 = Input(Pixel)
        out1 = Output(Unsigned(8))

        def body(self):
            w = Wire()
            w <<= self.in1
            self.out1 <<= w.r

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

@pytest.mark.skip(reason="This is a test for something that only the new Composite infrastructure can handle well")
def test_type_propagation_through_reg():
    class top(Module):
        clk = ClkPort
        rst = RstPort

        in1 = Input(Pixel)
        out1 = Output(Unsigned(8))

        def body(self):
            w = Wire()
            w <<= Reg(self.in1)
            self.out1 <<= w.r

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_reg_struct():
    class top(Module):
        sout1 = Output(Pixel)
        uout1 = Output(Pixel)
        uout2 = Output(Pixel)
        uout3 = Output(Pixel)
        uout4 = Output(Pixel)
        uin1 = Input(Pixel)
        uin2 = Input(Pixel)
        clk1 = Input(logic)
        clk2 = Input(logic)

        def body(self):
            clk = self.clk1
            self.sout1 <<= Reg(self.uin1, clock_port=self.clk1)
            registered = Reg(self.uin2)
            self.uout1 <<= registered
            reset_reg = Reg(self.uin1, reset_value_port=self.uin2, reset_port=self.uin2.r[4])
            reset = self.uin2.r[0]
            reset_reg2 = Reg(self.uin1, reset_value_port=self.uin2)
            with self.clk2 as clk:
                self.uout2 <<= Reg(self.uin2)
            #self.uout3 = Reg(self.uin1)
            clk = self.clk1
            self.uout3 <<= Reg(self.uin1)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_struct_of_struct():
    class ValidPixel(Struct):
        pixel = Pixel
        valid = logic

    class AlphaBender(Module):
        in1 = Input(ValidPixel)
        in2 = Input(ValidPixel)
        alpha = Input(Unsigned(8))
        outp = Output(ValidPixel)
        error = Output(logic)

        def body(self):

            def blend_mono(in1, in2):
                pix1 = in1 * self.alpha
                pix2 = in2 * (255-self.alpha)
                return (pix1 + pix2 + 127)[15:8]
            self.outp.pixel.r <<= blend_mono(self.in1.pixel.r, self.in2.pixel.r)
            self.outp.pixel.g <<= blend_mono(self.in1.pixel.g, self.in2.pixel.g)
            self.outp.pixel.b <<= blend_mono(self.in1.pixel.b, self.in2.pixel.b)
            self.outp.valid <<= self.in1.valid & self.in2.valid
            self.error <<= self.in1.valid ^ self.in2.valid

    test.rtl_generation(AlphaBender, inspect.currentframe().f_code.co_name)



class GPixel(NetTypeFactory, net_type = Struct):
    @classmethod
    def construct(cls, net_type: Optional[Struct], length: int) -> Optional[Tuple[str, int]]:
        if net_type is not None:
            net_type.length = length # We'll need this later in AlphaBlender
            net_type.add_member("r", Unsigned(length))
            net_type.add_member("g", Unsigned(length))
            net_type.add_member("b", Unsigned(length))
        return (f"Pixel_{length}", length)


def test_generic_struct():

    class AlphaBender(Module):
        in1 = Input(GPixel(8))
        in2 = Input(GPixel(8))
        alpha = Input(Unsigned(8))
        outp = Output(GPixel(8))

        def body(self):
            pixel_width = 8

            def blend_mono(in1, in2):
                pix1 = in1 * self.alpha
                pix2 = in2 * ((2**pixel_width)-1-self.alpha)
                return (pix1 + pix2 + (2**(pixel_width)-1)-1)[15:8]
            self.outp.r <<= blend_mono(self.in1.r, self.in2.r)
            self.outp.g <<= blend_mono(self.in1.g, self.in2.g)
            self.outp.b <<= blend_mono(self.in1.b, self.in2.b)

    test.rtl_generation(AlphaBender, inspect.currentframe().f_code.co_name)

def test_struct_with_method():
    pixel_width = 12

    class Pixel(Struct):
        r = Unsigned(pixel_width)
        g = Unsigned(pixel_width)
        b = Unsigned(pixel_width)

        class Behaviors(Struct.Behaviors):
            def blend(self, other, alpha):

                def blend_mono(in1, in2):
                    pix1 = in1 * alpha
                    pix2 = in2 * (255-alpha)
                    top = self.r.get_net_type().length + 8 - 1
                    return (pix1 + pix2 + 127)[top:8]
                result = Wire(Pixel)
                result.r <<= blend_mono(self.r, other.r)
                result.g <<= blend_mono(self.g, other.g)
                result.b <<= blend_mono(self.b, other.b)
                return result

    class AlphaBender(Module):
        in1 = Input(Pixel)
        in2 = Input(Pixel)
        alpha = Input(Unsigned(8))
        outp = Output(Pixel)

        def body(self):
            self.outp <<= self.in1.blend(self.in2, self.alpha)

    test.rtl_generation(AlphaBender, inspect.currentframe().f_code.co_name)


def test_struct_to_number(mode: str = "rtl"):
    pixel_width = 8

    class Top(Module):
        in1 = Input(GPixel(pixel_width))
        outp = Output()

        def body(self):
            self.outp <<= explicit_adapt(self.in1, Unsigned(length=self.in1.get_num_bits()))

        def simulate(self):
            def test(r,g,b):
                self.in1.r <<= r
                self.in1.g <<= g
                self.in1.b <<= b
                yield 0
                expected = r << pixel_width * 2 | g << pixel_width | b
                actual = self.outp.sim_value
                assert actual == expected, f"Expected {expected:x}, got {actual:x} for rgb: {r:x},{g:x},{b:x}"

            yield 10
            for x in range(16):
                yield from test(x, 2*x, 3*x)
            print("Done")


    if mode == "rtl":
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(Top, "test_struct_to_number")

def test_number_to_struct(mode: str = "rtl"):
    pixel_width = 8

    class Top(Module):
        in1 = Input(Unsigned(pixel_width * 3))
        outp = Output(GPixel(pixel_width))

        def body(self):
            self.outp <<= explicit_adapt(self.in1, self.outp.get_net_type())

        def simulate(self):
            def test(r,g,b):
                self.in1 <<= r << pixel_width * 2 | g << pixel_width | b
                yield 0
                assert self.outp.r == r, f"Expected R {r:x}, got {self.outp.r.sim_value:x} for rgb: {r:x},{g:x},{b:x}"
                assert self.outp.g == g, f"Expected G {g:x}, got {self.outp.g.sim_value:x} for rgb: {r:x},{g:x},{b:x}"
                assert self.outp.b == b, f"Expected B {b:x}, got {self.outp.b.sim_value:x} for rgb: {r:x},{g:x},{b:x}"

            yield 10
            for x in range(16):
                yield from test(x, 2*x, 3*x)
            print("Done")


    if mode == "rtl":
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(Top, "test_struct_to_number")

def test_number_to_struct_sim():
    test_number_to_struct("sim")


def test_multi_assign(mode: str = "rtl"):
    pixel_width = 8

    class Top(Module):
        outp = Output(GPixel(pixel_width))
        outp2 = Output(GPixel(pixel_width))
        outp3 = Output(GPixel(pixel_width))

        def body(self):
            self.outp <<= GPixel(pixel_width)(0,1,2)
            self.outp2 <<= GPixel(pixel_width)(0x10,0x11,b=0x12)
            #self.outp3 <<= GPixel(pixel_width)(0x20,b=0x22)

        def simulate(self):
            yield 10
            print("Done")

    if mode == "rtl":
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(Top, "test_multi_assign")

# This should fail, but it doesn't: we shouldn't allow multiple drivers, even if they are through reversed members of interfaces
@pytest.mark.skip(reason="This test is failing at the moment: we shouldn't allow multiple drivers, even if they are through reversed members of interfaces")
def test_illegal_branch(mode: str = "rtl"):
    class If(Interface):
        fwd = logic
        rev = Reverse(logic)

    class Producer(Module):
        o = Output(If)

        def body(self):
            self.o.fwd <<= 1

    class Consumer(Module):
        i = Input(If)

        def body(self):
            self.i.rev <<= 0

    class Top(Module):
        def body(self):
            p = Producer()
            c1 = Consumer()
            c2 = Consumer()

            c1.i <<= p.o

        def simulate(self):
            yield 10
            print("Done")

    if mode == "rtl":
        with ExpectError(SyntaxErrorException):
            test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(Top, "test_illegal_branch")


def test_struct_sub_module(mode: str = "rtl"):
    pixel_width = 8

    class Sub(Module):
        in1 = Input(GPixel(pixel_width))
        in2 = Input(GPixel(pixel_width))
        outp = Output(GPixel(pixel_width))

        def body(self):
            self.outp <<= Select(1, self.in1, self.in2)

    class Top(Module):
        in1 = Input(GPixel(pixel_width))
        outp = Output()

        def body(self):
            self.outp <<= Sub(self.in1, self.in1)

    if mode == "rtl":
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        assert False

class Data(Interface):
    ready = Reverse(logic)
    valid = logic
    data = Unsigned(16)
    data2 = Signed(13)

def test_interface_wire(mode: str = "rtl"):
    class top(Module):
        in2 = Input(Data)
        out2 = Output(Data)

        def body(self):
            x1 = Wire(Data)
            #x2 = Wire(Data)

            x1 <<= self.in2
            #x2 <<= x1
            #self.out2 <<= x2
            self.out2 <<= x1

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_interface_wire2(mode: str = "rtl"):
    class top(Module):
        in2 = Input(Data)
        out2 = Output(Data)

        def body(self):
            x1 = Wire(Data)
            x2 = Wire(Data)

            x1 <<= self.in2
            x2 <<= x1
            self.out2 <<= x2

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_interface_wire3(mode: str = "rtl"):
    class top(Module):
        in2 = Input(Data)
        out2 = Output(Data)

        def body(self):
            x0 = self.in2
            x1 = Wire(Data)
            x2 = Wire(Data)
            x3 = self.out2

            x1 <<= self.in2
            x2 <<= x1
            self.out2 <<= x2

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


class BiDir(Interface):
    fwd = Unsigned(2)
    bwd = Reverse(logic)

def test_bidir_interface(mode: str = "rtl"):

    class mod(Module):
        mod_out = Output(BiDir)

        def body(self):
            pass
            self.mod_out.fwd <<= 2

    class top(Module):
        top_in = Input(BiDir)

        def body(self):
            top_w = Wire(BiDir)

            #m = mod()
            #top_w <<= m()
            top_w <<= self.top_in

            top_w.bwd <<= 1
            top_w.bwd.BBB = True
            print(f"source: {hex(id(top_w.bwd._partial_sources[0][1].far_end))}, top_w.bwd: {hex(id(top_w.bwd))}, sink: {hex(id(first(top_w.bwd._sinks.keys())))}")
            pass

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)



class GenIf(Interface):
    fwd = GenericMember

def test_generic_interface(mode: str = "rtl"):

    class mod(Module):
        mod_out = Output(GenIf)

        def body(self):
            x = Wire(Unsigned(8))
            x <<= 42
            self.mod_out.fwd <<= x

    class top(Module):
        o = Output()

        def body(self):
            top_if = Wire(GenIf)

            mmm = mod()
            top_if <<= mmm.mod_out

            self.o <<= top_if.fwd


    test.rtl_generation(top, inspect.currentframe().f_code.co_name)



class GenIfR(Interface):
    rev = Reverse(GenericMember)

def test_generic_interface_rev(mode: str = "rtl"):

    class mod(Module):
        mod_out = Output(GenIfR)
        x = Output()
        def body(self):
            self.x <<= 42 & self.mod_out.rev

    class top(Module):
        i = Input(Unsigned(4))
        o = Output()
        def body(self):
            top_if = Wire(GenIfR)

            mmm = mod()
            top_if <<= mmm.mod_out
            top_if.rev <<= self.i
            self.o <<= mmm.x



    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


class GenIf2(Interface):
    fwd = GenericMember


def test_generic_interface2():
    class Consumer(Module):
        clk = ClkPort()
        rst = RstPort()
        inp = Input(GenIf2)

        def body(self):
            self.x = Reg(self.inp.fwd)


    class Producer(Module):
        clk = ClkPort()
        rst = RstPort()
        outp = Output(GenIf2)

        def body(self):
            x = Wire(Unsigned(8))
            x <<= Reg(Unsigned(8)(x+1))
            self.outp.fwd <<= x

    class top(Module):
        clk = ClkPort()
        rst = RstPort()

        def body(self):
            c = Consumer()
            p = Producer()
            c.inp <<= p.outp

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_member_type_propagation(mode: str = "rtl"):
    class Top(Module):
        inp = Input(ApbIf(Unsigned(32), Unsigned(32)))
        outp = Output(ApbIf(Unsigned(32)))

        class Inner(Module):
            i_inp = Input(ApbIf(Unsigned(32)))
            i_outp = Output(ApbIf(Unsigned(32)))

            def body(self):
                self.i_outp <<= self.i_inp

        def body(self):
            self.outp <<= Top.Inner(self.inp)

    if mode == "rtl":
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(Top, "test_multi_assign")

if __name__ == "__main__":
    #test_select_struct()
    #test_select_one_struct()
    #test_select_first_struct("rtl")
    #test_select_first_struct("sim")
    #test_reg_struct()
    #test_struct_of_struct()
    #test_generic_struct()
    #test_struct_with_method()
    #test_struct_to_number("rtl")
    #test_struct_to_number("sim")
    #test_struct_sub_module("rtl")
    #test_number_to_struct("rtl")
    #test_number_to_struct("sim")
    #test_interface_wire("rtl")
    #test_interface_wire2("rtl")
    #test_interface_wire3("rtl")
    #test_number_to_struct_sim()
    #test_multi_assign("sim")
    #test_select_one_struct_default()
    #test_type_propagation()
    #test_type_propagation_through_reg()
    #test_bidir_interface()
    #test_illegal_branch()
    #test_generic_interface()
    #test_generic_interface_rev()
    #test_generic_interface2()
    test_member_type_propagation()

"""
Additional tests needed:

    a[3].pink <<= blue
    blue <<= a[0].yellow

Simulation has different behavior, so that needs to be tested as well
"""