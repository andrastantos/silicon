#!/usr/bin/python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / ".."))

from typing import *

from silicon import *
from test_utils import *

import inspect

MyArray = Array(Unsigned(8), 4)

def test_array_assign():
    class top(Module):
        out_port = Output(MyArray)
        in1 = Input(MyArray)

        def body(self):
            self.out_port <<= self.in1

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_array_slice1():
    class top(Module):
        out_port1 = Output(Unsigned(8))
        #out_port2 = Output(Unsigned(8))
        #out_port3 = Output(Unsigned(8))
        #out_port4 = Output(Unsigned(8))
        in1 = Input(MyArray)

        def body(self):
            self.out_port1 <<= self.in1[0]

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


if __name__ == "__main__":
    #test_array_assign()
    test_array_slice1()
