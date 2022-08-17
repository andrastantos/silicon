import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".."))
sys.path.append(str(Path(__file__).parent / ".."/ "unit_tests"))

from typing import *

from silicon import *
from test_utils import *
import inspect

TByte = Unsigned(length=8)

class Test(Module):
    out_1 = Output(TByte)
    out_1b = Output(TByte)
    out_2 = Output(TByte)

    __test__ = False

    def body(self):
        self.out_1 <<= "8'b00001111"
        self.out_1b <<= "8'b00001111"
        try:
            self.out_2 <<= "something wrong"
            assert False
        except SyntaxErrorException:
            pass


def test_test():
    test.rtl_generation(Test, "test_string_typo")


if __name__ == "__main__":
    #test_sim()
    #test_verilog()
    test_test()