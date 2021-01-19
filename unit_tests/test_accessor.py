import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".."))
sys.path.append(str(Path(__file__).parent / ".."/ "unit_tests"))

from typing import *

from silicon import *
from test_utils import *
import inspect

TByte = Unsigned(length=8)

class Parity(Module):
    input = Input(TByte)
    output = Output(logic)

    def body(self):
        self.output <<= self.input[0]

class Test(Module):
    in_a = Input(TByte)
    out_1 = Output(TByte)
    out_2 = Output(TByte)
    out_3 = Output(TByte)

    __test__ = False

    def body(self):
        self.out_1 <<= Parity(self.in_a)
        self.out_2 <<= Parity(self.in_a)

def test_test():
    test.rtl_generation(Test, "test_accessor")


if __name__ == "__main__":
    #test_sim()
    #test_verilog()
    test_test()