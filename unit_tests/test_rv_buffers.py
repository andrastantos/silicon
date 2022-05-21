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

class RvSource(GenericModule):
    output_port = Output()
    clock_port = AutoInput(auto_port_names=("clk", "clk_port", "clock", "clock_port"), optional=False)
    reset_port = AutoInput(auto_port_names=("rst", "rst_port", "reset", "reset_port"), optional=True)

    def construct(self, data_type = None, generator = None, max_wait_state: int = 5):
        if data_type is not None:
            self.output_port.set_net_type(data_type)
        if generator is not None:
            self.generator = generator
        self.max_wait_state = max_wait_state

    def body(self):
        self.data_members = Wire(self.output_port.get_data_member_type())
        self.output_port.set_data_members(self.data_members)

    def simulate(self) -> TSimEvent:
        def reset():
            self.output_port.valid <<= 0
            self.wait_state = randint(1,self.max_wait_state+1)

        reset()
        while True:
            yield (self.clock_port, )
            edge_type = self.clock_port.get_sim_edge()
            if edge_type == EdgeType.Positive:
                if self.reset_port.sim_value == 1:
                    reset()
                else:
                    if self.wait_state == 0 and self.output_port.ready.sim_value == 1:
                        self.wait_state = randint(1,self.max_wait_state+1)
                    if self.wait_state != 0:
                        self.wait_state -= 1
                        if self.wait_state == 0:
                            self.data_members <<= self.generator()
                            #self.output_port.set_data_members(self.generator())
                    self.output_port.valid <<= 1 if self.wait_state == 0 else 0


class RvSink(GenericModule):
    input_port = Input()
    clock_port = AutoInput(auto_port_names=("clk", "clk_port", "clock", "clock_port"), optional=False)
    reset_port = AutoInput(auto_port_names=("rst", "rst_port", "reset", "reset_port"), optional=True)

    def construct(self, checker = None, max_wait_state: int = 5):
        if checker is not None:
            self.checker = checker
        self.max_wait_state = max_wait_state

    def body(self):
        self.data_members = Wire(self.input_port.get_data_member_type())
        self.data_members <<= self.input_port.get_data_members()

    def simulate(self) -> TSimEvent:
        def reset():
            self.input_port.ready <<= 0
            self.wait_state = randint(1,self.max_wait_state+1)

        reset()
        while True:
            yield (self.clock_port, )
            edge_type = self.clock_port.get_sim_edge()
            if edge_type == EdgeType.Positive:
                if self.reset_port.sim_value == 1:
                    reset()
                else:
                    if self.wait_state == 0 and self.input_port.valid.sim_value == 1:
                        self.wait_state = randint(1,self.max_wait_state+1)
                        self.checker(self.data_members.sim_value)
                    if self.wait_state != 0:
                        self.wait_state -= 1
                    self.input_port.ready <<= 1 if self.wait_state == 0 else 0


class RvData(ReadyValid):
    data = Unsigned(8)
class Generator(RvSource):
    def construct(self, max_wait_state: int = 5):
        super().construct(RvData(), None, max_wait_state)
        self.cnt = -1
    def generator(self):
        self.cnt += 1
        if self.cnt == 256:
            self.cnt = 0
        return (self.cnt, )

class Checker(RvSink):
    def construct(self, max_wait_state: int = 5):
        super().construct(None, max_wait_state)
        self.cnt = 0
        self.last_val = Wire(Unsigned(8))
    def checker(self, value):
        self.last_val <<= value[0]
        assert(value[0] == self.cnt)
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
    #test_forward_buf("sim")
    test_gen_chk("sim")