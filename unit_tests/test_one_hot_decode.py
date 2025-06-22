#!pytest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".."))
from silicon import *
from silicon.utils import VerbosityLevels
import test_utils as t
import inspect
import pytest

# Some of the simplest tests

def test_one_hot_decode(mode: str = "rtl"):
    class Top(Module):
        input_port = Input(Unsigned(4))
        output1 = Output(logic)
        output2 = Output(logic)
        def body(self):
            decoder = OneHotDecode()
            decoder.input_port <<= self.input_port
            self.output1 <<= decoder.decode(0)
            self.output2 <<= decoder.decode(5)

    set_verbosity_level(VerbosityLevels.instantiation)
    if mode == "rtl":
        t.test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        t.test.simulation(Top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)




if __name__ == "__main__":
    test_one_hot_decode("rtl")