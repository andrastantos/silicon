#!/usr/bin/python3

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".."))

from typing import *

from silicon import *
from test_utils import *

def test_wire_array():
    # NOTE: this generates an empty SV file because none of the internal wires have explicit names
    #       and there's no output generated.
    class test_module(Module):
        data_in = Input(Unsigned(length=2))
        def body(self):
            self.pen_colors = []
            for i in range(2):
                self.pen_colors.append(Wire(Unsigned(length=1)))
            for i in range(2):
                self.pen_colors[i] <<= self.data_in[i]
    test.rtl_generation(test_module, "test_wire_array")

def test_wire_array2():
    class test_module(Module):
        data_in = Input(Unsigned(length=2))
        out1 = Output(Unsigned(length=2))
        def body(self):
            self.pen_colors = []
            direct_wire = self.data_in[0] ^ self.data_in[1]
            for i in range(2):
                self.pen_colors.append(Wire(Unsigned(length=1)))
            for i in range(2):
                self.pen_colors[i] <<= (and_gate, or_gate)[i](*self.data_in)
            for i in range(2):
                self.out1[i] = self.pen_colors[i]

    test.rtl_generation(test_module, "test_wire_array2")

if __name__ == "__main__":
    test_wire_array()
    #test_wire_array2()


