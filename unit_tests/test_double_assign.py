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
        #self.output <<= self.input[0] ^ self.input[1] ^ self.input[2] ^ self.input[3] ^ self.input[4] ^ self.input[5] ^ self.input[6] ^ self.input[7]
        pass

class Test(Module):
    in_a = Input(TByte)
    out_h = Output(TByte)

    __test__ = False

    def body(self):
        self.out_h <<= Parity(self.in_a)
        try:
            self.out_h <<= self.in_a
            assert False
        except SyntaxErrorException:
            pass


def test_test():
    test.rtl_generation(Test, "test_double_assign")


if __name__ == "__main__":
    #test_sim()
    #test_verilog()
    test_test()