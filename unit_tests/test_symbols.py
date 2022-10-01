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

def test_local_global_collision():
    class top(Module):
        in_1 = Input(logic)
        out_1 = Output(logic)

        def body(self):
            out_1 = Wire(logic)
            self.out_1 <<= out_1
            out_1 <<= self.in_1


    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

class GPixel(NetTypeFactory, net_type = Struct):
    @classmethod
    def construct(cls, net_type: Optional[Struct], length: int, prefix: str="") -> Optional[Tuple[str, int, str]]:
        if net_type is not None:
            net_type.length = length # We'll need this later in AlphaBlender
            net_type.add_member(prefix+"r", Unsigned(length))
            net_type.add_member(prefix+"g", Unsigned(length))
            net_type.add_member(prefix+"b", Unsigned(length))
        return (f"Pixel_{length}_{prefix}", f"{length},{prefix}")

def test_composite_component_collision():
    class top(Module):
        in_1 = Input(GPixel(8))
        out_1 = Output(GPixel(8))
        out_1_r = Output(logic)
        def body(self):
            self.out_1 <<= self.in_1

    with ExpectError(SyntaxErrorException):
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_composite_component_collision2():
    class top(Module):
        in_1 = Input(GPixel(8))
        in_1_r = Output(logic)
        out_1 = Output(GPixel(8))
        def body(self):
            self.out_1 <<= self.in_1

    with ExpectError(SyntaxErrorException):
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_composite_component_collision3():
    class top(Module):
        in_1 = Input(GPixel(8))
        out_1 = Output(GPixel(8))
        def body(self):
            in_1_r = Wire(Unsigned(8))
            in_1 = Wire(GPixel(8))
            in_1 <<= self.in_1
            self.out_1 <<= in_1
            in_1_r <<= self.in_1.r


    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_composite_component_collision4():
    class top(Module):
        input1_1 = Input(GPixel(8, prefix=""))
        input1 = Input(GPixel(8, prefix="1_"))
        out_1 = Output(GPixel(8))
        def body(self):
            pass

    with ExpectError(SyntaxErrorException):
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)

@pytest.mark.skip(reason="This test is broken at the moment: it generates a bunch of unnamed wires, instead of named ones. Will have to re-enable once refactoring of Composites is complete")
def test_composite_component_collision5():
    class top(Module):
        in_1 = Input(GPixel(8))
        out_1 = Output(GPixel(8))
        clk = ClkPort()
        def body(self):
            # All of these should be conflicting in the end
            con                   = Wire(GPixel(8, "flict_ing_sym_bol_"))
            con_flict             = Wire(GPixel(8, "ing_sym_bol_"))
            con_flict_ing         = Wire(GPixel(8, "sym_bol_"))
            con_flict_ing_sym     = Wire(GPixel(8, "bol_"))
            con_flict_ing_sym_bol = Wire(GPixel(8))
            con.flict_ing_sym_bol_r <<= Reg(self.in_1.r)
            con_flict.ing_sym_bol_r <<= Reg(con.flict_ing_sym_bol_r)
            con_flict_ing.sym_bol_r <<= Reg(con_flict.ing_sym_bol_r)
            con_flict_ing_sym.bol_r <<= Reg(con_flict_ing.sym_bol_r)
            con_flict_ing_sym_bol.r <<= Reg(con_flict_ing_sym.bol_r)

            con.flict_ing_sym_bol_g <<= Reg(self.in_1.g)
            con_flict.ing_sym_bol_g <<= Reg(con.flict_ing_sym_bol_g)
            con_flict_ing.sym_bol_g <<= Reg(con_flict.ing_sym_bol_g)
            con_flict_ing_sym.bol_g <<= Reg(con_flict_ing.sym_bol_g)
            con_flict_ing_sym_bol.g <<= Reg(con_flict_ing_sym.bol_g)

            con.flict_ing_sym_bol_b <<= Reg(self.in_1.b)
            con_flict.ing_sym_bol_b <<= Reg(con.flict_ing_sym_bol_b)
            con_flict_ing.sym_bol_b <<= Reg(con_flict.ing_sym_bol_b)
            con_flict_ing_sym.bol_b <<= Reg(con_flict_ing.sym_bol_b)
            con_flict_ing_sym_bol.b <<= Reg(con_flict_ing_sym.bol_b)

            self.out_1 <<= con_flict_ing_sym_bol

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


if __name__ == "__main__":
    #test_named_sub_modules()
    #test_sub_module_name_collision()
    #test_wire_sub_module_name_collision()
    #test_local_global_collision()
    #test_composite_component_collision()
    #test_composite_component_collision2()
    #test_composite_component_collision3()
    #test_composite_component_collision4()
    test_composite_component_collision5()