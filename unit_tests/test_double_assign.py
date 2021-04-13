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
    input_port = Input(TByte)
    output_port = Output(logic)

    def body(self):
        #self.output_port <<= self.input_port[0] ^ self.input_port[1] ^ self.input_port[2] ^ self.input_port[3] ^ self.input_port[4] ^ self.input_port[5] ^ self.input_port[6] ^ self.input_port[7]
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