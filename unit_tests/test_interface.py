#!/usr/bin/python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / ".."))

from typing import *

from silicon import *
from test_utils import *
import inspect

def test_interface1(mode = "rtl"):
    class MyInterface(Interface):
        data = Unsigned(8)
        ready = Reverse(logic)
        valid = logic

    class top(Module):
        in_a = Input(MyInterface)
        out_a = Output(MyInterface)

        def body(self):
            pass

    class top_tb(top):
        def simulate(self):
            yield 10
            print("Done")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(top_tb, "test_interface1_sim")

def test_interface1_sim():
    test_interface1("sim")

def test_interface2(mode = "rtl"):
    class MyInterface(Interface):
        data = Unsigned(8)
        ready = Reverse(logic)
        valid = logic

    class top(Module):
        in_a = Input(MyInterface)
        out_a = Output(MyInterface)

        def body(self):
            self.out_a = self.in_a

    class top_tb(top):
        def simulate(self):
            yield 10
            print("Done")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(top_tb, "test_interface2_sim")

def test_interface3(mode = "rtl"):
    class MyInterface(Interface):
        data = Unsigned(8)
        ready = Reverse(logic)
        valid = logic

    class top(Module):
        in_a = Input(MyInterface)
        out_a = Output(MyInterface)
        x_in = Input(Unsigned(8))

        def body(self):
            #self.out_a = self.in_a
            self.out_a.data <<= self.x_in
            self.in_a.ready <<= self.out_a.ready & self.in_a.valid

    class top_tb(top):
        def simulate(self):
            yield 10
            print("Done")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(top_tb, "test_interface2_sim")

def test_composite_interface(mode = "rtl"):
    class Channel(Interface):
        data = Unsigned(8)
        ready = Reverse(logic)
        valid = logic
    class BusIf(Interface):
        data_write_bus = Channel
        addr_write_bus = Channel
        resp_write_bus = Reverse(Channel)
        data_read_bus = Reverse(Channel)
        addr_read_bus = Channel

    class top(Module):
        side_a = Input(BusIf)
        side_b = Output(BusIf)

        def body(self):
            self.side_b.data_write_bus.data[3:0] <<= self.side_a.data_write_bus.data[7:4]
            self.side_b.data_write_bus.data[7:4] <<= self.side_a.data_write_bus.data[3:0]

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    #else:
    #    test.simulation(top_tb, "test_interface2_sim")

def test_composite_interface2(mode = "rtl"):
    class Channel(Interface):
        data = Unsigned(8)
        ready = Reverse(logic)
        valid = logic
    class BusIf(Interface):
        data_write_bus = Channel
        addr_write_bus = Channel
        resp_write_bus = Reverse(Channel)
        data_read_bus = Reverse(Channel)
        addr_read_bus = Channel

    class top(Module):
        side_a = Input(BusIf)
        side_b = Output(BusIf)

        def body(self):
            self.side_b <<= self.side_a

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    #else:
    #    test.simulation(top_tb, "test_interface2_sim")

def test_composite_interface3(mode = "rtl"):
    class Channel(Interface):
        data = Unsigned(8)
        ready = Reverse(logic)
        valid = logic
    class BusIf(Interface):
        data_write_bus = Channel
        addr_write_bus = Channel
        resp_write_bus = Reverse(Channel)
        data_read_bus = Reverse(Channel)
        addr_read_bus = Channel

    class top(Module):
        side_a = Input(BusIf)
        side_b = Output(BusIf)

        def body(self):
            self.side_b.addr_write_bus <<= self.side_a.addr_write_bus

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    #else:
    #    test.simulation(top_tb, "test_interface2_sim")

def test_composite_interface4(mode = "rtl"):
    class Channel(Interface):
        data = Unsigned(8)
        ready = Reverse(logic)
        valid = logic
    class BusIf(Interface):
        data_write_bus = Channel
        addr_write_bus = Channel
        resp_write_bus = Reverse(Channel)
        data_read_bus = Reverse(Channel)
        addr_read_bus = Channel

    class top(Module):
        side_a = Input(BusIf)
        side_b = Output(BusIf)

        def body(self):
            self.side_b.addr_write_bus <<= self.side_b.resp_write_bus

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    #else:
    #    test.simulation(top_tb, "test_interface2_sim")

if __name__ == "__main__":
    #test_interface1("sim")
    #test_interface2("rtl")
    #test_interface3("rtl")
    #test_composite_interface("rtl")
    #test_composite_interface2("rtl")
    #test_composite_interface3("rtl")
    test_composite_interface4("rtl")


