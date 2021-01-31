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
        (MemoryPortConfig(
            addr_type = Unsigned(8),
            data_type = Unsigned(8),
            registered_input = True,
            registered_output = False
        ),),
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
                (MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_in.get_net_type(),
                    registered_input = registered_input,
                    registered_output = registered_output
                ),),
                reset_content = None
            )
            mem = Memory(config)
            mem.data_in <<= self.data_in
            self.data_out <<= mem.data_out
            mem.addr <<= self.addr
            mem.write_en = self.write_en

        def simulate(self) -> TSimEvent:
            def clk() -> int:
                yield 10
                self.clk <<= ~self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0
            
            self.clk <<= 1
            self.write_en <<= 0
            yield 10
            for i in range(10):
                yield from clk()
            self.data_in <<= 0
            self.addr <<= 0
            self.write_en <<= 1
            yield from clk()
            self.addr <<= 1
            self.write_en <<= 0
            yield from clk()
            if registered_input:
                yield from clk()
            assert self.data_in.sim_value == 0
            yield from clk()
            self.write_en <<= 1
            self.data_in <<= 3
            yield from clk()
            if registered_input:
                yield from clk()
            assert self.data_in.sim_value == 3
            yield from clk()
            

    if mode == "rtl":
        test.rtl_generation(Top(), inspect.currentframe().f_back.f_code.co_name)
    else:
        test.simulation(Top, "_test_single_port_ram")

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





def test_single_port_async_rom(mode: str = "rtl"):

    class Top(Module):
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        clk = Input(logic)

        def body(self):
            config = MemoryConfig(
                (MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_out.get_net_type(),
                    registered_input = False,
                    registered_output = False
                ),),
                reset_content = "xxx.bin"
            )
            mem = Memory(config)
            self.data_out <<= mem.data_out
            mem.addr <<= self.addr

    if mode == "rtl":
        test.rtl_generation(Top(), inspect.currentframe().f_code.co_name)

def test_single_port_rom(mode: str = "rtl"):

    class Top(Module):
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        clk = Input(logic)

        def body(self):
            config = MemoryConfig(
                (MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_out.get_net_type(),
                    registered_input = True,
                    registered_output = False
                ),),
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
            def rom_content(data_bits, addr_bits):
                i = 0
                while True:
                    yield i
                    i += 1

            config = MemoryConfig(
                (MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_out.get_net_type(),
                    registered_input = True,
                    registered_output = False
                ),),
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
            def rom_content(data_bits, addr_bits):
                i = 0
                for data in range(20):
                    yield i
                    i += 1

            config = MemoryConfig(
                (MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_out.get_net_type(),
                    registered_input = True,
                    registered_output = False
                ),),
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
            def rom_content(data_bits, addr_bits):
                i = 0
                for data in range(20):
                    yield i
                    i += 1

            config = MemoryConfig(
                (MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_out.get_net_type(),
                    registered_input = True,
                    registered_output = True
                ),),
                reset_content = rom_content
            )
            mem = Memory(config)
            self.data_out <<= mem.data_out
            mem.addr <<= self.addr

    if mode == "rtl":
        test.rtl_generation(Top(), inspect.currentframe().f_code.co_name)

READ_WRITE = 3
READ = 1
WRITE = 2
def _test_simple_dual_port_ram(mode: str, registered_input_a: bool, registered_output_a: bool, registered_input_b: bool, registered_output_b: bool, port_a: int = READ_WRITE, port_b: int = READ_WRITE):

    class Top(Module):
        data_in_a = Input(Unsigned(14))
        data_out_a = Output(Unsigned(14))
        data_in_b = Input(Unsigned(14))
        data_out_b = Output(Unsigned(14))
        addr_a = Input(Unsigned(6))
        addr_b = Input(Unsigned(6))
        write_en_a = Input(logic)
        write_en_b = Input(logic)
        clk = Input(logic)

        def body(self):
            config = MemoryConfig(
                (MemoryPortConfig(
                    addr_type = self.addr_a.get_net_type(),
                    data_type = self.data_in_a.get_net_type(),
                    registered_input = registered_input_a,
                    registered_output = registered_output_a
                ),
                MemoryPortConfig(
                    addr_type = self.addr_b.get_net_type(),
                    data_type = self.data_in_b.get_net_type(),
                    registered_input = registered_input_b,
                    registered_output = registered_output_b
                ),),
                reset_content = "config.bin"
            )
            mem = Memory(config)
            if port_a & READ != 0:
                self.data_out_a <<= mem.port1_data_out
            if port_a & WRITE != 0:
                mem.port1_data_in <<= self.data_in_a
                mem.port1_write_en = self.write_en_a
            mem.port1_addr <<= self.addr_a

            if port_b & READ != 0:
                self.data_out_b <<= mem.port2_data_out
            if port_b & WRITE != 0:
                mem.port2_data_in <<= self.data_in_b
                mem.port2_write_en = self.write_en_b
            mem.port2_addr <<= self.addr_b

    if mode == "rtl":
        test.rtl_generation(Top(), inspect.currentframe().f_back.f_code.co_name)

def test_simple_dual_port_ram_ffff(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, False, False, False, False)

def test_simple_dual_port_ram_ffft(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, False, False, False, True)

def test_simple_dual_port_ram_fftf(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, False, False, True, False)

def test_simple_dual_port_ram_fftt(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, False, False, True, True)

def test_simple_dual_port_ram_ftff(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, False, True, False, False)

def test_simple_dual_port_ram_ftft(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, False, True, False, True)

def test_simple_dual_port_ram_fttf(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, False, True, True, False)

def test_simple_dual_port_ram_fttt(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, False, True, True, True)

def test_simple_dual_port_ram_tfff(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, True, False, False, False)

def test_simple_dual_port_ram_tfft(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, True, False, False, True)

def test_simple_dual_port_ram_tftf(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, False, True, False)

def test_simple_dual_port_ram_tftt(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, False, True, True)

def test_simple_dual_port_ram_ttff(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, True, True, False, False)

def test_simple_dual_port_ram_ttft(mode: str = "rtl"):
    with ExpectError(SyntaxErrorException):
        _test_simple_dual_port_ram(mode, True, True, False, True)

def test_simple_dual_port_ram_tttf(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, True, True, False)

def test_simple_dual_port_ram_tttt(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, True, True, True)

def test_simple_dual_port_ram_rw(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, False, True, False, READ, WRITE)

class Pixel(Struct):
    r = Unsigned(8)
    g = Unsigned(8)
    b = Unsigned(8)

def test_struct_ram(mode: str = "rtl", registered_input: bool = True, registered_output: bool = False):
    class Top(Module):
        data_in = Input(Pixel())
        data_out = Output(Pixel())
        addr = Input(Unsigned(8))
        write_en = Input(logic)
        clk = Input(logic)

        def body(self):
            config = MemoryConfig(
                (MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_in.get_net_type(),
                    registered_input = registered_input,
                    registered_output = registered_output
                ),),
                reset_content = None
            )
            mem = Memory(config)
            mem.data_in <<= self.data_in
            self.data_out <<= mem.data_out
            mem.addr <<= self.addr
            mem.write_en = self.write_en

        def simulate(self) -> TSimEvent:
            def clk() -> int:
                yield 10
                self.clk <<= ~self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0
            
            self.clk <<= 1
            self.write_en <<= 0
            yield 10
            for i in range(10):
                yield from clk()
            self.data_in <<= 0
            self.addr <<= 0
            self.write_en <<= 1
            yield from clk()
            self.addr <<= 1
            self.write_en <<= 0
            yield from clk()
            if registered_input:
                yield from clk()
            assert self.data_in.sim_value == 0
            yield from clk()
            self.write_en <<= 1
            self.data_in <<= 3
            yield from clk()
            if registered_input:
                yield from clk()
            assert self.data_in.sim_value == 3
            yield from clk()
            

    if mode == "rtl":
        test.rtl_generation(Top(), inspect.currentframe().f_code.co_name)
    else:
        test.simulation(Top, "_test_single_port_ram")

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
    #test_single_port_rom4("rtl")
    #test_simple_dual_port_ram_tftf("rtl")
    #test_simple_dual_port_ram_tftt("rtl")
    #test_simple_dual_port_ram_tttf("rtl")
    #test_simple_dual_port_ram_tttt("rtl")
    #test_single_port_async_rom("rtl")
    #test_simple_dual_port_ram_rw("rtl")

    #test_single_port_ram_tt("sim")
    test_struct_ram("rtl")