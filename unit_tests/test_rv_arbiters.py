#!/usr/bin/python3
from random import randint, random
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / ".."))

from typing import *

from silicon import *
from test_utils import *

import inspect

class Request(ReadyValid):
    data = Unsigned(16)


class Response(ReadyValid):
    data = Unsigned(16)

responses = []
requests = []

class ReqGenerator(RvSimSource):
    def construct(self, top_byte: int, expectation_queue, max_wait_state: int = 5):
        super().construct(Request, None, max_wait_state)
        self.cnt = -1
        self.top_byte = top_byte
        self.expected_responses = expectation_queue

    def generator(self, is_reset, simulator: Simulator):
        if is_reset:
            return None
        self.cnt += 1
        if self.cnt == 256:
            self.cnt = 0
        val = self.cnt + (self.top_byte << 8)
        requests.append(val)
        self.expected_responses.append(val)
        return val

class ReqChecker(RvSimSink):
    def construct(self, max_wait_state: int = 5):
        super().construct(None, max_wait_state)
    def checker(self, value, simulator: Simulator):
        data = int(value.data)
        simulator.SimAssert(data in requests)
        requests.remove(data)
        responses.append(data)

class RspGenerator(RvSimSource):
    def construct(self, top_byte: int, max_wait_state: int = 5):
        super().construct(Response, None, max_wait_state)
        self.cnt = -1
        self.top_byte = top_byte
    def generator(self, is_reset, simulator):
        if is_reset:
            return None
        rsp = responses[0]
        responses.pop(0)
        return rsp

class RspChecker(RvSimSource, RvSimSink):
    def construct(self, top_byte: int, expectation_queue, max_wait_state: int = 5):
        super().construct(None, max_wait_state)
        self.cnt = -1
        self.top_byte = top_byte
        self.expected_responses = expectation_queue

    def checker(self, value, simulator: Simulator):
        simulator.sim_assert(value.data == self.expected_responses[0])
        self.expected_responses.pop(0)


def test_arbiter_buf(mode: str = "sim"):
    class top(Module):
        req1 = Input(Request)
        rsp1 = Output(Response)
        req2 = Input(Request)
        rsp2 = Output(Response)
        clk = ClkPort()
        rst = RstPort()

        def body(self):
            fb = ForwardBuf()
            fb.input_port <<= self.in1
            self.out1 <<= fb.output_port

    class sim_top(Module):
        clk = ClkPort()
        rst = RstPort()
        def body(self):
            self.data = Wire(RvData)
            self.checker_module = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker_module.input_port <<= dut(self.data)

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
        in1 = Input(RvData)
        out1 = Output(RvData)
        clk = ClkPort()
        rst = RstPort()

        def body(self):
            self.out1 <<= ReverseBuf(self.in1)

    class sim_top(Module):
        clk = ClkPort()
        rst = RstPort()
        def body(self):
            self.data = Wire(RvData)
            self.checker_module = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker_module.input_port <<= dut(self.data)

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
        in1 = Input(RvData)
        out1 = Output(RvData)
        clk = ClkPort()
        rst = RstPort()

        def body(self):
            dut = Fifo(depth=10)
            self.out1 <<= dut(self.in1)

    class sim_top(Module):
        clk = ClkPort()
        rst = RstPort()
        def body(self):
            self.data = Wire(RvData)
            self.checker_module = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker_module.input_port <<= dut(self.data)

        def simulate(self) -> TSimEvent:
            def clk() -> int:
                yield 10
                self.clk <<= ~self.clk & self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0

            print("Simulation started")

            self.generator.max_wait_state = 10
            self.checker_module.max_wait_state = 2
            self.rst <<= 1
            self.clk <<= 1
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 5
            self.checker_module.max_wait_state = 5
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 2
            self.checker_module.max_wait_state = 10
            for i in range(500):
                yield from clk()
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(sim_top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)

def test_zero_delay_fifo(mode: str = "rtl"):
    class top(Module):
        in1 = Input(RvData)
        out1 = Output(RvData)
        clk = ClkPort()
        rst = RstPort()

        def body(self):
            dut = ZeroDelayFifo(depth=10)
            self.out1 <<= dut(self.in1)

    class sim_top(Module):
        clk = ClkPort()
        rst = RstPort()
        def body(self):
            self.data = Wire(RvData)
            self.checker_module = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker_module.input_port <<= dut(self.data)

        def simulate(self) -> TSimEvent:
            def clk() -> int:
                yield 10
                self.clk <<= ~self.clk & self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0

            print("Simulation started")

            self.generator.max_wait_state = 10
            self.checker_module.max_wait_state = 2
            self.rst <<= 1
            self.clk <<= 1
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 5
            self.checker_module.max_wait_state = 5
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 2
            self.checker_module.max_wait_state = 10
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
        in1 = Input(RvData)
        out1 = Output(RvData)
        clk = ClkPort()
        rst = RstPort()

        def body(self):
            dut = DelayLine(depth=5)
            self.out1 <<= dut(self.in1)

    class sim_top(Module):
        clk = ClkPort()
        rst = RstPort()
        def body(self):
            self.data = Wire(RvData)
            self.checker_module = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker_module.input_port <<= dut(self.data)

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

            self.generator.max_wait_state = 10
            self.checker_module.max_wait_state = 2
            for i in range(100):
                yield from clk()
            self.generator.max_wait_state = 0
            self.checker_module.max_wait_state = 0
            for i in range(100):
                yield from clk()
            self.generator.max_wait_state = 2
            self.checker_module.max_wait_state = 10
            for i in range(100):
                yield from clk()
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(sim_top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)



def test_pacer(mode: str = "rtl"):
    class top(Module):
        in1 = Input(RvData)
        out1 = Output(RvData)
        clk = ClkPort()
        rst = RstPort()

        def body(self):
            dut = Pacer(3)
            self.out1 <<= dut(self.in1)

    class sim_top(Module):
        clk = ClkPort()
        rst = RstPort()
        def body(self):
            self.data = Wire(RvData)
            self.checker_module = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker_module.input_port <<= dut(self.data)

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
            self.checker_module.max_wait_state = 1
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 2
            self.checker_module.max_wait_state = 5
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 5
            self.checker_module.max_wait_state = 2
            for i in range(500):
                yield from clk()
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(sim_top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)

def test_stage(mode: str = "sim"):
    class top(Module):
        in1 = Input(RvData)
        out1 = Output(RvData)
        clk = ClkPort()
        rst = RstPort()

        class SampleStage(Module):
            in1 = Input(RvData)
            out1 = Output(RvData)
            clk = ClkPort()
            rst = RstPort()

            def body(self):
                stage = Stage()

                class States(Enum):
                    idle = 0
                    one = 1
                    two = 2
                    three = 3
                    four = 4

                stage.input_port    <<= self.in1
                stage.reset_value   <<= States.idle
                stage.idle_state    <<= States.idle

                stage_input = Wire(self.in1.get_data_member_type())
                stage_input <<= stage.stage_input

                count = stage_input.data[1:0]

                stage.add_transition(States.idle, count == 0, States.idle)
                stage.add_transition(States.idle, count == 1, States.one)
                stage.add_transition(States.idle, count == 2, States.two)
                stage.add_transition(States.idle, count == 3, States.three)
                stage.add_transition(States.one, 1, States.idle)
                stage.add_transition(States.two, 1, States.one)
                stage.add_transition(States.three, 1, States.two)

                stage.stage_output <<= stage_input

                self.out1.valid <<= stage.output_valid
                stage.output_ready <<= self.out1.ready
                self.out1.data <<= stage_input.data

        def body(self):
            dut = top.SampleStage()
            self.out1 <<= dut(self.in1)

    class sim_top(Module):
        clk = ClkPort()
        rst = RstPort()
        def body(self):
            self.data = Wire(RvData)
            self.checker_module = Checker()
            self.generator = Generator()
            self.data <<= self.generator.output_port
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.checker_module.input_port <<= dut(self.data)

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
            self.checker_module.max_wait_state = 1
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 2
            self.checker_module.max_wait_state = 5
            for i in range(500):
                yield from clk()
            self.generator.max_wait_state = 5
            self.checker_module.max_wait_state = 2
            for i in range(500):
                yield from clk()
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(sim_top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)

def test_forward_buf_sim():
    test_forward_buf("sim")

def test_reverse_buf_sim():
    test_reverse_buf("sim")

def test_fifo_sim():
    test_fifo("sim")

def test_zero_delay_fifo_sim():
    test_zero_delay_fifo("sim")

def test_gen_chk_sim():
    test_gen_chk("sim")

def test_delay_line_sim():
    test_delay_line("sim")

def test_pacer_sim():
    test_pacer("sim")

if __name__ == "__main__":
    #test_forward_buf("rtl")
    #test_reverse_buf("rtl")
    #test_fifo("rtl")
    #test_forward_buf("sim")
    #test_reverse_buf("sim")
    #test_fifo("sim")
    test_zero_delay_fifo("sim")
    #test_gen_chk("rtl")
    #test_gen_chk("sim")
    #test_delay_line("sim")
    #test_pacer("sim")
    #test_stage("rtl")
    #test_stage("sim")
