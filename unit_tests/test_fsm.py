import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".."))
sys.path.append(str(Path(__file__).parent / ".."/ "unit_tests"))

from typing import *

from silicon import *
from test_utils import *
import inspect
from enum import Enum

class UseFSM(Module):
    # We're implementing a simple checksum module: get inputs until 'last', then output the sum of all received inputs
    clk = ClkPort()
    rst = RstPort()

    data_in_valid = Input(logic)
    data_last = Input(logic)
    data_in = Input(Unsigned(8))
    data_out = Output(Unsigned(8))
    data_out_valid = Output(logic)

    def body(self) -> None:
        my_fsm = FSM()
        self.my_fsm = my_fsm # Will need it during generate to save PDF

        class States(Enum):
            reset = 0
            idle = 1
            get_data = 2
            get_wait = 3
            get_first_data = 4
            send_data = 5

        my_fsm.reset_value <<= States.reset
        my_fsm.default_state <<= States.idle

        # You don't have to list transitions in any particular order. Do what makes sense for you
        my_fsm.add_transition(States.reset, 1, States.idle) # Always enter idle from reset
        my_fsm.add_transition(States.idle, self.data_in_valid & ~self.data_last, States.get_first_data)
        my_fsm.add_transition(States.get_data, ~self.data_in_valid, States.get_wait)
        my_fsm.add_transition(States.get_data, self.data_in_valid & ~self.data_last, States.get_data)
        my_fsm.add_transition(States.get_wait, ~self.data_in_valid, States.get_wait)
        my_fsm.add_transition(States.get_wait, self.data_in_valid & ~self.data_last, States.get_data)
        my_fsm.add_transition(States.get_data, self.data_in_valid & self.data_last, States.send_data)
        my_fsm.add_transition(States.get_wait, self.data_in_valid & self.data_last, States.send_data)
        my_fsm.add_transition(States.idle, self.data_in_valid & self.data_last, States.send_data)
        my_fsm.add_transition(States.send_data, ~self.data_in_valid, States.idle)
        my_fsm.add_transition(States.send_data, self.data_in_valid & ~self.data_last, States.get_first_data)
        my_fsm.add_transition(States.send_data, self.data_in_valid & self.data_last, States.send_data)
        my_fsm.add_transition(States.get_first_data, ~self.data_in_valid, States.get_wait)
        my_fsm.add_transition(States.get_first_data, self.data_in_valid & ~self.data_last, States.get_data)
        my_fsm.add_transition(States.get_first_data, self.data_in_valid & self.data_last, States.send_data)

        my_sum = Wire(Unsigned(8))
        next_my_sum = Wire(Unsigned(8))
        next_my_sum <<= SelectOne(
            my_fsm.next_state == States.reset, 0,
            my_fsm.next_state == States.idle, 0,
            my_fsm.next_state == States.get_first_data, self.data_in,
            my_fsm.next_state == States.get_data, (my_sum + self.data_in)[7:0],
            my_fsm.next_state == States.get_wait, my_sum,
            my_fsm.next_state == States.send_data, (my_sum + self.data_in)[7:0]
        )
        my_sum <<= Reg(next_my_sum)
        self.data_out <<= my_sum
        self.data_out_valid <<= my_fsm.state == States.send_data
    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        ret_val = super().generate(netlist, back_end)
        graph = self.my_fsm.draw(self, netlist, back_end)
        graph.render("my_fsm")
        return ret_val

def test_fsm_gen():
    test.rtl_generation(UseFSM, "test_fsm_gen")

def test_fsm_sim():
    class UseFSM_tb(UseFSM):
        def simulate(self):
            def clk() -> int:
                yield 10
                self.clk <<= ~self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0

            def send_packet(byte_cnt: int, wait_cnt: int, initial_sum: int = 0):
                from random import randint
                chksum = initial_sum
                for idx in range(byte_cnt):
                    data = randint(0, 255)
                    chksum += data
                    last = idx == byte_cnt - 1
                    self.data_in <<= data
                    self.data_in_valid <<= 1
                    self.data_last <<= last
                    yield from clk()
                    if not last:
                        for wait in range(wait_cnt):
                            self.data_in_valid <<= 0
                            yield from clk()
                self.data_in_valid <<= 0
                self.expected_checksum = chksum & 255

            print("Simulation started")
            self.rst <<= 1
            self.clk <<= 1
            yield 10
            for i in range(5):
                yield from clk()
            print("Reset removed")
            self.rst <<= 0
            for i in range(5):
                yield from clk()

            yield from send_packet(5,0)
            yield from clk()
            assert self.data_out_valid == 1
            assert self.data_out == self.expected_checksum

            for i in range(5):
                yield from clk()

            yield from send_packet(1,0)
            yield from clk()
            assert self.data_out_valid == 1
            assert self.data_out == self.expected_checksum
            yield from send_packet(3,0)
            yield from clk()
            assert self.data_out_valid == 1
            assert self.data_out == self.expected_checksum
            yield from send_packet(4,0)
            self.data_in <<= 33
            self.data_in_valid <<= 1
            self.data_last <<= 0
            yield from clk()
            assert self.data_out_valid == 1
            assert self.data_out == self.expected_checksum
            yield from send_packet(5,0,33)
            yield from clk()
            assert self.data_out_valid == 1
            assert self.data_out == self.expected_checksum
            yield from send_packet(5,4)
            yield from clk()
            assert self.data_out_valid == 1
            assert self.data_out == self.expected_checksum
            print("Simulation ended")

    test.simulation(UseFSM_tb, "test_fsm_sim")

def test_const_fsm(mode="rtl"):
    class Top(Module):
        clk = ClkPort()
        rst = RstPort()

        def body(self):
            self.decode_fsm = FSM()

            self.decode_fsm.reset_value <<= 11
            self.decode_fsm.default_state <<= 12

            # We have serious problems with constant generation IFF we access state before any of the edge assignments
            # This doesn't happen if:
            # - We create some other gates (compare clk for example)
            # - If the access happens *after* the transition declarations
            # It does happen though if either state or next_state is accessed
            shouldnt_matter = Wire(Number(min_val=11,max_val=12))
            shouldnt_matter <<= self.decode_fsm.next_state

            # We're in a state where we don't have anything partial
            terminal_fsm_state = Wire(logic)
            self.decode_fsm.add_transition(11, 1, 12)

    if mode == "rtl":
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(Top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)

if __name__ == "__main__":
    test_fsm_gen()
    #test_fsm_sim()
    #test_const_fsm()