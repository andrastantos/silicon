#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__),".."))

from typing import *

from silicon import *
from test_utils import *
import pytest

import inspect

def test_single_port_ram_no_ports(mode: str = "rtl"):
    config = MemoryConfig(
        MemoryPortConfig(
            addr_type = Unsigned(8),
            data_type = Unsigned(8),
            registered_input = True,
            registered_output = False
        ),
        None,
        reset_content = None
    )

    if mode == "rtl":
        with ExpectError(SyntaxErrorException):
            test.rtl_generation(Memory(config), inspect.currentframe().f_code.co_name)

def _test_single_port_ram(mode: str, registered_input: bool, registered_output: bool):

    class Top(Module):
        data_in = Input(Unsigned(8))
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        write_en = Input(logic)
        clk = Input(logic)

        def body(self):
            config = MemoryConfig(
                MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_in.get_net_type(),
                    registered_input = registered_input,
                    registered_output = registered_output
                ),
                None,
                reset_content = None
            )
            mem = Memory(config)
            mem.data_in <<= self.data_in
            self.data_out <<= mem.data_out
            mem.addr <<= self.addr
            mem.write_en = self.write_en

    if mode == "rtl":
        test.rtl_generation(Top(), inspect.currentframe().f_back.f_code.co_name)

def test_single_port_ram_ff(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_single_port_ram(mode, False, False)

def test_single_port_ram_ft(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_single_port_ram(mode, False, True)

def test_single_port_ram_tf(mode: str = "rtl"):
    _test_single_port_ram(mode, True, False)

def test_single_port_ram_tt(mode: str = "rtl"):
    _test_single_port_ram(mode, True, True)





def test_single_port_rom(mode: str = "rtl"):

    class Top(Module):
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        clk = Input(logic)

        def body(self):
            config = MemoryConfig(
                MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_out.get_net_type(),
                    registered_input = True,
                    registered_output = False
                ),
                None,
                reset_content = "xxx.bin"
            )
            mem = Memory(config)
            self.data_out <<= mem.data_out
            mem.addr <<= self.addr

    if mode == "rtl":
        test.rtl_generation(Top(), inspect.currentframe().f_code.co_name)

def test_single_port_rom2(mode: str = "rtl"):

    class Top(Module):
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        clk = Input(logic)

        def body(self):
            def rom_content():
                i = 0
                while True:
                    yield i
                    i += 1

            config = MemoryConfig(
                MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_out.get_net_type(),
                    registered_input = True,
                    registered_output = False
                ),
                None,
                reset_content = rom_content
            )
            mem = Memory(config)
            self.data_out <<= mem.data_out
            mem.addr <<= self.addr

    if mode == "rtl":
        test.rtl_generation(Top(), inspect.currentframe().f_code.co_name)

def test_single_port_rom3(mode: str = "rtl"):

    class Top(Module):
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        clk = Input(logic)

        def body(self):
            def rom_content():
                i = 0
                for data in range(20):
                    yield i
                    i += 1

            config = MemoryConfig(
                MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_out.get_net_type(),
                    registered_input = True,
                    registered_output = False
                ),
                None,
                reset_content = rom_content
            )
            mem = Memory(config)
            self.data_out <<= mem.data_out
            mem.addr <<= self.addr

    if mode == "rtl":
        test.rtl_generation(Top(), inspect.currentframe().f_code.co_name)

def test_single_port_rom4(mode: str = "rtl"):

    class Top(Module):
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        clk = Input(logic)

        def body(self):
            def rom_content():
                i = 0
                for data in range(20):
                    yield i
                    i += 1

            config = MemoryConfig(
                MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_out.get_net_type(),
                    registered_input = True,
                    registered_output = True
                ),
                None,
                reset_content = rom_content
            )
            mem = Memory(config)
            self.data_out <<= mem.data_out
            mem.addr <<= self.addr

    if mode == "rtl":
        test.rtl_generation(Top(), inspect.currentframe().f_code.co_name)

# TODO:
# - Test all 8 combinations of registered in/out
# - Test various address and data-types (structs for example)
# - Test dual-port memories
# - Test simulation

if __name__ == "__main__":
    #test_single_port_ram_ff("rtl")
    #test_single_port_ram_ft("rtl")
    #test_single_port_ram_tf("rtl")
    #test_single_port_ram_tt("rtl")
    #test_single_port_rom("rtl")
    #test_single_port_rom2("rtl")
    #test_single_port_rom3("rtl")
    test_single_port_rom4("rtl")


