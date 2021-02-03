#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__),".."))

from typing import *

from silicon import *
from test_utils import *

import inspect

class Data(ReadyValid):
    data = Unsigned(16)
    data2 = Signed(13)

def test_forward_buf(mode: str = "rtl"):
    class top(Module):
        in1 = Input(Data())
        out1 = Output(Data())
        clk = Input(logic)
        rst = Input(logic)

        def body(self):
            fb = ForwardBuf()
            fb.input_port <<= self.in1
            self.out1 <<= fb.output_port
            
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_reverse_buf(mode: str = "rtl"):
    class top(Module):
        in1 = Input(Data())
        out1 = Output(Data())
        clk = Input(logic)
        rst = Input(logic)

        def body(self):
            self.out1 = ReverseBuf(self.in1)
            
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

if __name__ == "__main__":
    test_forward_buf("rtl")
    #test_reverse_buf("rtl")