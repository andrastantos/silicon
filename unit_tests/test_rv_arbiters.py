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
        simulator.sim_assert(data in requests)
        requests.remove(data)
        responses.append(data)

class RspGenerator(RvSimSource):
    def construct(self, max_wait_state: int = 5):
        super().construct(Response, None, max_wait_state)
        self.cnt = -1
    def generator(self, is_reset, simulator):
        if is_reset:
            return None
        rsp = responses[0]
        responses.pop(0)
        return rsp

class RspChecker(RvSimSink):
    def construct(self, top_byte: int, expectation_queue, max_wait_state: int = 5):
        super().construct(None, max_wait_state)
        self.cnt = -1
        self.top_byte = top_byte
        self.expected_responses = expectation_queue

    def checker(self, value, simulator: Simulator):
        simulator.sim_assert(value.data == self.expected_responses[0])
        self.expected_responses.pop(0)


@pytest.mark.skip(reason="Test is under development")
def test_arbiter_buf(mode: str = "sim"):
    class sim_top(Module):
        clk = ClkPort()
        rst = RstPort()
        def body(self):
            self.req1 = Wire(Request)
            self.rsp1 = Wire(Response)
            self.req2 = Wire(Request)
            self.rsp2 = Wire(Response)

            self.expectation_queue = []
            self.req1_gen = ReqGenerator(top_byte=0x11, expectation_queue=self.expectation_queue)
            self.req1_chk = RspChecker(top_byte=0x11, expectation_queue=self.expectation_queue)

            self.req2_gen = ReqGenerator(top_byte=0x22, expectation_queue=self.expectation_queue)
            self.req2_chk = RspChecker(top_byte=0x22, expectation_queue=self.expectation_queue)

            self.out_chk = ReqChecker()
            self.out_gen = RspGenerator()

            self.req1 <<= self.req1_gen.output_port
            self.req1_chk.input_port <<= self.rsp1
            self.req2 <<= self.req2_gen.output_port
            self.req2_chk.input_port <<= self.rsp2

            dut = RVArbiter(request_if=Request, response_if=Response)
            dut.req1_request <<= self.req1
            self.rsp1 <<= dut.req1_response
            dut.req2_request <<= self.req2
            self.rsp2 <<= dut.req2_response

            self.out_chk.input_port <<= dut.output_request
            dut.output_response <<= self.out_gen.output_port

            dut.arbitration_order.append("req1")
            dut.arbitration_order.append("req2")

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

if __name__ == "__main__":
    test_arbiter_buf("sim")