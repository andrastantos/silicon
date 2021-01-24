#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__),".."))

from typing import *

from silicon import *
from test_utils import *

import inspect

def test_select():
    class top(Module):
        sout1 = Output(Signed(length=5))
        uin1 = Input(Unsigned(length=2))
        uin2 = Input(Unsigned(length=4))
        sin1 = Input(Signed(length=4))
        sin2 = Input(Signed(length=4))
        sel_in = Input(Unsigned(2))

        def body(self):
            #self.sout1 = Select(self.sel_in, self.uin1, self.uin2, self.sin1, default=self.sin2)
            self.sout1 = Select(self.sel_in, self.uin1, self.uin2, self.sin1, self.sin2)
            
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_select_with_none():
    class top(Module):
        sout1 = Output(Signed(length=5))
        uin1 = Input(Unsigned(length=2))
        uin2 = Input(Unsigned(length=4))
        sin1 = Input(Signed(length=4))
        sin2 = Input(Signed(length=4))
        sel_in = Input(Unsigned(2))

        def body(self):
            #self.sout1 = Select(self.sel_in, self.uin1, self.uin2, self.sin1, default=self.sin2)
            self.sout1 = Select(self.sel_in, self.uin1, self.uin2, self.sin1, self.sin2, None)
            
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_mux():
    class top(Module):
        in1 = Input(Unsigned(length=4))
        in2 = Input(Unsigned(length=4))
        sel = Input(logic)
        out1 = Output(Unsigned(length=4))

        def body(self):
            self.out1 = Select(self.sel, self.in1, self.in2)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_select_one_first():
    class top(Module):
        sout1 = Output(Signed(length=11))
        sout2 = Output(Signed(length=11))
        sout3 = Output(Signed(length=11))
        sout4 = Output(Signed(length=11))
        sout5 = Output(Signed(length=11))
        val_in1 = Input(Unsigned(length=2))
        val_in2 = Input(Unsigned(length=4))
        val_in3 = Input(Signed(length=4))
        val_in4 = Input(Signed(length=4))
        default = Input(Unsigned(length=8))
        sel_in1 = Input(Unsigned(length=2))
        sel_in2 = Input(Unsigned(length=1))
        sel_in3 = Input(Signed(length=2))
        sel_in4 = Input(Signed(length=1))

        def body(self):
            self.sout1 = SelectOne(self.sel_in1, self.val_in1, self.sel_in2, self.val_in2, self.sel_in3, self.val_in3, self.sel_in4, self.val_in4, default=self.default)
            self.sout2 = SelectFirst(self.sel_in1, self.val_in1, self.sel_in2, self.val_in2, self.sel_in3, self.val_in3, self.sel_in4, self.val_in4, default=self.default)
            self.sout3 = SelectFirst(self.sel_in1, self.val_in1, self.sel_in2, self.val_in2, self.sel_in3, self.val_in3, selector_3=self.sel_in4, value_3=self.val_in4, default=self.default)
            self.sout4 = SelectFirst(self.sel_in1, self.val_in1, self.sel_in2, self.val_in2, self.sel_in3, self.val_in3, value_3=self.val_in4, selector_3=self.sel_in4, default=self.default)
            self.sout5 = SelectFirst(
                selector_2=self.sel_in3, value_2=self.val_in3,
                selector_1=self.sel_in2, value_1=self.val_in2,
                selector_3=self.sel_in4, value_3=self.val_in4,
                selector_0=self.sel_in1, value_0=self.val_in1,
                default=self.default
            )
            
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_reg():
    class top(Module):
        sout1 = Output(Signed(length=5))
        uout1 = Output(Signed(length=5))
        uout2 = Output(Signed(length=5))
        uout3 = Output(Signed(length=5))
        uout4 = Output(Signed(length=5))
        uin1 = Input(Unsigned(length=2))
        uin2 = Input(Unsigned(length=4))
        clk1 = Input(logic)
        clk2 = Input(logic)

        def body(self):
            clk = self.clk1
            self.sout1 = Reg(self.uin1, clock_port=self.clk1)
            registered = Reg(self.uin2)
            self.uout1 = registered
            reset_reg = Reg(self.uin1, reset_value_port=3, reset_port=self.uin2[1])
            reset = self.uin2[0]
            reset_reg2 = Reg(self.uin1, reset_value_port=2)
            with self.clk2 as clk:
                self.uout2 = Reg(self.uin2)
            #self.uout3 = Reg(self.uin1)
            clk = self.clk1
            self.uout3 = Reg(self.uin1)
            
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_reg3():
    class top(Module):
        sout1 = Output(Signed(length=5))
        uout1 = Output(Signed(length=5))
        uout2 = Output(Signed(length=5))
        uout3 = Output(Signed(length=5))
        uout4 = Output(Signed(length=5))
        uin1 = Input(Unsigned(length=2))
        uin2 = Input(Unsigned(length=4))
        clk = Input(logic)
        clk2 = Input(logic)

        def body(self):
            clk = self.clk
            self.sout1 = Reg(self.uin1, clock_port=self.clk)
            registered = Reg(self.uin2)
            self.uout1 = registered
            reset_reg = Reg(self.uin1, reset_value_port=3, reset_port=self.uin2[1])
            reset = self.uin2[0]
            reset_reg2 = Reg(self.uin1, reset_value_port=2)
            with self.clk2 as clk:
                self.uout2 = Reg(self.uin2)
            self.uout3 = Reg(self.uin1)
            
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_reg4():
    class top(Module):
        sout1 = Output(Signed(length=5))
        uin1 = Input(Unsigned(length=2))
        clk1 = Input(logic)

        def body(self):
            self.sout1 = Reg(self.uin1, clock_port=(self.clk1 & self.uin1[0]))
            
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


if __name__ == "__main__":
    #test_select()
    #test_select_one_first()
    #test_reg()
    #test_reg3()
    #test_mux()
    #test_select_with_none()
    test_reg4()