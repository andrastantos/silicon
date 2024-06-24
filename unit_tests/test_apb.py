#!/usr/bin/python3
from random import randint, random
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / ".."))

from typing import *

from silicon import *
from test_utils import *

import inspect
from dataclasses import dataclass
from copy import copy

Apb8Bus = ApbIf(Unsigned(8), Unsigned(8))

@dataclass
class TransferDesc(object):
    is_write: bool
    addr: int
    data: int



# APB signalling
#
#             <-- read -->      <-- write ->
#     CLK     \__/^^\__/^^\__/^^\__/^^\__/^^\__/^^\__/
#     psel    ___/^^^^^^^^^^^\_____/^^^^^^^^^^^\______
#     penable _________/^^^^^\___________/^^^^^\______
#     pready  ---------/^^^^^\-----------/^^^^^\------
#     pwrite  ---/^^^^^^^^^^^\-----\___________/------
#     paddr   ---<===========>-----<===========>------
#     prdata  ---------<=====>------------------------
#     pwdata  ---------------------<===========>------

class ApbGenerator(GenericModule):
    clk = ClkPort()
    rst = RstPort()

    apb: ApbBaseIf = Output()
    def construct(self, transfer_queue, if_type):
        self.transfer_queue = transfer_queue
        self.apb.set_net_type(if_type)

    def simulate(self, simulator):
        def clk() -> TSimEvent:
            yield (self.clk, )
            edge_type = self.clk.get_sim_edge()
            while edge_type != EdgeType.Positive:
                yield (self.clk, )
                edge_type = self.clk.get_sim_edge()
            simulator.log(f"returning from clk()")

        def issue_write(addr, data):
            self.apb.psel <<= 1
            self.apb.penable <<= 0

            self.apb.pwrite <<= 1
            self.apb.paddr <<= addr
            self.apb.pwdata <<= data
            yield from clk()
            self.apb.penable <<= 1
            self.transfer_queue.append(TransferDesc(is_write=True, addr=addr, data=data))
            yield from clk()
            while self.apb.pready == 0: yield from clk()
            self.apb.pwrite <<= None
            self.apb.pwdata <<= None
            self.apb.psel <<= 0
            self.apb.penable <<= 0

        def issue_read(addr):
            self.apb.psel <<= 1
            self.apb.penable <<= 0

            self.apb.pwrite <<= 0
            self.apb.paddr <<= addr
            self.apb.pwdata <<= None
            yield from clk()
            self.apb.penable <<= 1
            self.transfer_queue.append(TransferDesc(is_write=False, addr=addr, data=None))
            yield from clk()
            while self.apb.pready == 0: yield from clk()
            self.apb.pwrite <<= None
            self.apb.pwdata <<= None
            self.apb.psel <<= 0
            self.apb.penable <<= 0

            return copy(self.apb.prdata.sim_value)

        yield from clk()
        while self.rst == 1:
            yield from clk()
        for _ in range(5):
            yield from clk()

        yield from issue_write(0x00, 0x01)
        yield from issue_write(0x01, 0xff)
        yield from issue_write(0x00, 0x00)
        yield from issue_write(0x00, 0xf0)
        read_val = yield from issue_read(0x00)
        simulator.sim_assert(read_val == 0xf9)


@pytest.mark.parametrize("mode", ("sim","rtl"))
def test_apb_reg(mode: str):

    class top(Module):
        clk = ClkPort()
        rst = RstPort()
        apb = Input(Apb8Bus)
        bit0 = Output(logic)
        stat3 = Input(logic)

        def body(self):
            reg = APBReg(address=0)
            self.high_nibble = reg.add_field(name="HighNibble", high_bit=7, low_bit=4, kind=APBReg.Kind.ctrl).ctrl_port
            lsb = reg.add_field(name="lsb", high_bit=0, low_bit=0, kind=APBReg.Kind.both)
            lsb.stat_port <<= self.high_nibble[0]
            self.bit0 <<= lsb.ctrl_port
            reg.add_field(name="bit3", high_bit=3, low_bit=3, kind=APBReg.Kind.stat).stat_port <<= self.stat3
            reg.apb_bus <<= self.apb

    def create_arbiter():
        return GenericRVArbiter(request_if=Request, response_if=Response, max_oustanding_responses=10, arbitration_algorithm=arbitration_algorithm)
    class sim_top(Module):
        clk = ClkPort()
        rst = RstPort()

        def body(self):
            self.transfers = []

            apb_generator = ApbGenerator(self.transfers, Apb8Bus)

            dut = top()
            dut.apb <<= apb_generator.apb
            dut.stat3 <<= 1

        def simulate(self) -> TSimEvent:
            def clk() -> TSimEvent:
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
            for i in range(50):
                yield from clk()
            now = yield 10
            print(f"Done at {now}")

    test_name = f"{inspect.currentframe().f_code.co_name.lower()}"
    if mode == "rtl":
        test.rtl_generation(top, test_name=test_name)
    else:
        test.simulation(sim_top, test_name=test_name)


if __name__ == "__main__":
    test_apb_reg("sim")
