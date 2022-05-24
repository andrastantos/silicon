#!/usr/bin/python3
from random import randint, random
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


class RvData(ReadyValid):
    data = Unsigned(8)

class Generator(RvSimSource):
    def construct(self, max_wait_state: int = 5):
        super().construct(RvData(), None, max_wait_state)
        self.cnt = -1
    def generator(self):
        self.cnt += 1
        if self.cnt == 256:
            self.cnt = 0
        return self.cnt

class Checker(RvSimSink):
    def construct(self, max_wait_state: int = 5):
        super().construct(None, max_wait_state)
        self.cnt = 0
        self.last_val = Wire(Unsigned(8))
    def checker(self, value):
        self.last_val <<= value
        assert(value == self.cnt)
        self.cnt += 1
        if self.cnt == 256:
            self.cnt = 0


def test_gen_chk(mode: str = "rtl"):
    class top(Module):
        clk = Input(logic)
        rst = Input(logic)

        def body(self):
            self.data = Wire(RvData())
            self.checker = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            self.checker.input_port <<= self.data

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
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0
            for i in range(500):
                yield from clk()
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(top, inspect.currentframe().f_code.co_name)


def test_forward_buf(mode: str = "rtl"):
    class top(Module):
        in1 = Input(RvData())
        out1 = Output(RvData())
        clk = Input(logic)
        rst = Input(logic)

        def body(self):
            fb = ForwardBuf()
            fb.input_port <<= self.in1
            self.out1 <<= fb.output_port

    class sim_top(Module):
        clk = Input(logic)
        rst = Input(logic)
        def body(self):
            self.data = Wire(RvData())
            self.checker = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker.input_port <<= dut(self.data)

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
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0
            for i in range(500):
                yield from clk()
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(sim_top, inspect.currentframe().f_code.co_name)

def test_reverse_buf(mode: str = "rtl"):
    class top(Module):
        in1 = Input(RvData())
        out1 = Output(RvData())
        clk = Input(logic)
        rst = Input(logic)

        def body(self):
            self.out1 = ReverseBuf(self.in1)

    class sim_top(Module):
        clk = Input(logic)
        rst = Input(logic)
        def body(self):
            self.data = Wire(RvData())
            self.checker = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker.input_port <<= dut(self.data)

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
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0
            for i in range(500):
                yield from clk()
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(sim_top, inspect.currentframe().f_code.co_name)


def test_fifo(mode: str = "rtl"):
    class top(Module):
        in1 = Input(RvData())
        out1 = Output(RvData())
        clk = Input(logic)
        rst = Input(logic)

        def body(self):
            dut = Fifo(depth=10)
            self.out1 = dut(self.in1)

    class sim_top(Module):
        clk = Input(logic)
        rst = Input(logic)
        def body(self):
            self.data = Wire(RvData())
            self.checker = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker.input_port <<= dut(self.data)

        def simulate(self) -> TSimEvent:
            def clk() -> int:
                yield 10
                self.clk <<= ~self.clk & self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0

            print("Simulation started")

            self.generator.max_wait_state = 10
            self.checker.max_wait_state = 2
            self.rst <<= 1
            self.clk <<= 1
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 5
            self.checker.max_wait_state = 5
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 2
            self.checker.max_wait_state = 10
            for i in range(500):
                yield from clk()
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(sim_top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)


def test_delay_line(mode: str = "rtl"):
    class top(Module):
        in1 = Input(RvData())
        out1 = Output(RvData())
        clk = Input(logic)
        rst = Input(logic)

        def body(self):
            dut = DelayLine(depth=5)
            self.out1 = dut(self.in1)

    class sim_top(Module):
        clk = Input(logic)
        rst = Input(logic)
        def body(self):
            self.data = Wire(RvData())
            self.checker = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker.input_port <<= dut(self.data)

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
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0

            #self.generator.max_wait_state = 10
            #self.checker.max_wait_state = 2
            #for i in range(500):
            #    yield from clk()
            self.generator.max_wait_state = 5
            self.checker.max_wait_state = 5
            for i in range(500):
                yield from clk()
            #self.generator.max_wait_state = 2
            #self.checker.max_wait_state = 10
            #for i in range(500):
            #    yield from clk()
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(sim_top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)



def test_pacer(mode: str = "rtl"):
    class top(Module):
        in1 = Input(RvData())
        out1 = Output(RvData())
        clk = Input(logic)
        rst = Input(logic)

        def body(self):
            dut = Pacer(3)
            self.out1 = dut(self.in1)

    class sim_top(Module):
        clk = Input(logic)
        rst = Input(logic)
        def body(self):
            self.data = Wire(RvData())
            self.checker = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker.input_port <<= dut(self.data)

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
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0

            self.generator.max_wait_state = 1
            self.checker.max_wait_state = 1
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 2
            self.checker.max_wait_state = 5
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 5
            self.checker.max_wait_state = 2
            for i in range(500):
                yield from clk()
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(sim_top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)


if __name__ == "__main__":
    #test_forward_buf("rtl")
    #test_reverse_buf("rtl")
    #test_fifo("rtl")
    #test_forward_buf("sim")
    #test_reverse_buf("sim")
    #test_fifo("sim")
    #test_gen_chk("sim")
    #test_delay_line("sim")
    test_pacer("sim")