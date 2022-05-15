#!/usr/bin/python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / ".."))

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

        def simulate(self) -> TSimEvent:
            def clk() -> int:
                yield 10
                self.clk <<= ~self.clk & self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0

            print("Simulation started")

            self.rst <<= 1
            self.clk <<= 1
            self.in1.valid <<= 0
            self.out1.ready <<= 0
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0
            for i in range(5):
                yield from clk()
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(top, inspect.currentframe().f_code.co_name)

def test_reverse_buf(mode: str = "rtl"):
    class top(Module):
        in1 = Input(Data())
        out1 = Output(Data())
        clk = Input(logic)
        rst = Input(logic)

        def body(self):
            self.out1 = ReverseBuf(self.in1)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


def test_fifo(mode: str = "rtl"):
    class top(Module):
        in1 = Input(Data())
        out1 = Output(Data())
        clk = Input(logic)
        rst = Input(logic)

        def body(self):
            self.out1 = Fifo(depth=10)(self.in1)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


if __name__ == "__main__":
    #test_forward_buf("rtl")
    #test_reverse_buf("rtl")
    #test_fifo("rtl")
    test_forward_buf("sim")