#!/usr/bin/python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / ".."))

from typing import *

from silicon import *
from silicon.memory import _BasicMemory

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
        clk = ClkPort()

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
            mem.write_en <<= self.write_en

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
        test.rtl_generation(Top, inspect.currentframe().f_back.f_code.co_name)
    else:
        test.simulation(Top, "_test_single_port_ram")

def test_single_port_ram_ff(mode: str = "rtl"):
    _test_single_port_ram(mode, False, False)

def test_single_port_ram_ft(mode: str = "rtl"):
    _test_single_port_ram(mode, False, True)

def test_single_port_ram_tf(mode: str = "rtl"):
    _test_single_port_ram(mode, True, False)

def test_single_port_ram_tt(mode: str = "rtl"):
    _test_single_port_ram(mode, True, True)





def test_single_port_async_rom(mode: str = "rtl"):

    class Top(Module):
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        clk = ClkPort()

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
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

def test_single_port_rom(mode: str = "rtl"):

    class Top(Module):
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        clk = ClkPort()

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
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

def test_single_port_rom2(mode: str = "rtl"):

    class Top(Module):
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        clk = ClkPort()

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
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

def test_single_port_rom3(mode: str = "rtl"):

    class Top(Module):
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        clk = ClkPort()

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
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

def test_single_port_rom4(mode: str = "rtl"):

    class Top(Module):
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        clk = ClkPort()

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
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)

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
        clk = ClkPort()

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
                mem.port1_write_en <<= self.write_en_a
            mem.port1_addr <<= self.addr_a

            if port_b & READ != 0:
                self.data_out_b <<= mem.port2_data_out
            if port_b & WRITE != 0:
                mem.port2_data_in <<= self.data_in_b
                mem.port2_write_en <<= self.write_en_b
            mem.port2_addr <<= self.addr_b

    if mode == "rtl":
        test.rtl_generation(Top, inspect.currentframe().f_back.f_code.co_name)

def test_simple_dual_port_ram_ffff(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, False, False, False, False)

def test_simple_dual_port_ram_ffft(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, False, False, False, True)

def test_simple_dual_port_ram_fftf(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, False, False, True, False)

def test_simple_dual_port_ram_fftt(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, False, False, True, True)

def test_simple_dual_port_ram_ftff(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, False, True, False, False)

def test_simple_dual_port_ram_ftft(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, False, True, False, True)

def test_simple_dual_port_ram_fttf(mode: str = "rtl"):
        _test_simple_dual_port_ram(mode, False, True, True, False)

def test_simple_dual_port_ram_fttt(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, False, True, True, True)

def test_simple_dual_port_ram_tfff(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, False, False, False)

def test_simple_dual_port_ram_tfft(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, False, False, True)

def test_simple_dual_port_ram_tftf(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, False, True, False)

def test_simple_dual_port_ram_tftt(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, False, True, True)

def test_simple_dual_port_ram_ttff(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, True, False, False)

def test_simple_dual_port_ram_ttft(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, True, False, True)

def test_simple_dual_port_ram_tttf(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, True, True, False)

def test_simple_dual_port_ram_tttt(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, True, True, True)

def test_simple_dual_port_ram_rw(mode: str = "rtl"):
    _test_simple_dual_port_ram(mode, True, False, True, False, READ, WRITE)






def test_simple_dual_port_ram_sim(mode = "sim", read_new_data_a = True, read_new_data_b = True):

    class Top(Module):
        data_in_a = Input(Unsigned(14))
        data_out_a = Output(Unsigned(14))
        data_in_b = Input(Unsigned(14))
        data_out_b = Output(Unsigned(14))
        addr_a = Input(Unsigned(6))
        addr_b = Input(Unsigned(6))
        write_en_a = Input(logic)
        write_en_b = Input(logic)
        clk = ClkPort()

        def body(self):
            # This config reads new data
            config = MemoryConfig(
                (MemoryPortConfig(
                    addr_type = self.addr_a.get_net_type(),
                    data_type = self.data_in_a.get_net_type(),
                    registered_input = read_new_data_a,
                    registered_output = not read_new_data_a
                ),
                MemoryPortConfig(
                    addr_type = self.addr_b.get_net_type(),
                    data_type = self.data_in_b.get_net_type(),
                    registered_input = read_new_data_b,
                    registered_output = not read_new_data_b
                ),),
                reset_content = "config.bin"
            )
            mem = Memory(config)
            self.data_out_a <<= mem.port1_data_out
            mem.port1_data_in <<= self.data_in_a
            mem.port1_write_en <<= self.write_en_a
            mem.port1_addr <<= self.addr_a

            self.data_out_b <<= mem.port2_data_out
            mem.port2_data_in <<= self.data_in_b
            mem.port2_write_en <<= self.write_en_b
            mem.port2_addr <<= self.addr_b

        def simulate(self, simulator) -> TSimEvent:
            def clk() -> int:
                yield 10
                self.clk <<= ~self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0

            self.clk <<= 1
            self.write_en_a <<= 0
            self.write_en_b <<= 0
            for i in range(10):
                yield from clk()
            # Write from port a
            self.write_en_a <<= 1
            self.write_en_b <<= 0
            for i in range(10):
                self.data_in_a <<= i
                self.addr_a <<= i
                yield from clk()

            # Write from port b
            self.write_en_a <<= 0
            self.write_en_b <<= 1
            for i in range(10,20):
                self.data_in_b <<= i
                self.addr_b <<= i
                yield from clk()

            # Write from port a, read from port b
            self.write_en_a <<= 1
            self.write_en_b <<= 0
            for i in range(10):
                self.data_in_b <<= None
                data = i+0x100
                old_data = i
                self.data_in_a <<= data
                self.addr_a <<= i
                self.addr_b <<= i
                simulator.log(f"set addr to {i}")
                yield from clk()
                simulator.log(f"testing")
                # There's a one-cycle latency in getting the data back, so can't test the first loop in this simple manner
                if i > 0:
                    if read_new_data_a and read_new_data_b:
                        assert self.data_out_b == new_old_data, f"{self.data_out_b} == {new_old_data} failed"
                        assert self.data_out_a == new_data, f"{self.data_out_a} == {new_data} failed"
                    elif not read_new_data_a and read_new_data_b:
                        assert self.data_out_b == new_data, f"{self.data_out_b} == {new_old_data} failed"
                        assert self.data_out_a == new_old_data, f"{self.data_out_a} == {new_data} failed"
                    elif read_new_data_a and not read_new_data_b:
                        assert self.data_out_b == new_old_data, f"{self.data_out_b} == {new_old_data} failed"
                        assert self.data_out_a == new_data, f"{self.data_out_a} == {new_data} failed"
                    else:
                        assert self.data_out_b == new_old_data, f"{self.data_out_b} == {new_old_data} failed"
                        assert self.data_out_a == new_old_data, f"{self.data_out_a} == {new_data} failed"
                new_data = data
                new_old_data = old_data

            self.write_en_a <<= 0
            self.write_en_b <<= 1
            for i in range(10):
                self.data_in_a <<= None
                data = i+0x200
                old_data = i+0x100
                self.data_in_b <<= data
                self.addr_a <<= i
                self.addr_b <<= i
                simulator.log(f"set addr to {i}")
                yield from clk()
                simulator.log(f"testing")
                if i > 0:
                    if read_new_data_a and read_new_data_b:
                        assert self.data_out_b == new_data, f"{self.data_out_b} == {new_data} failed"
                        assert self.data_out_a == new_old_data, f"{self.data_out_a} == {new_data} failed"
                    elif not read_new_data_a and read_new_data_b:
                        assert self.data_out_b == new_data, f"{self.data_out_b} == {new_data} failed"
                        assert self.data_out_a == new_old_data, f"{self.data_out_a} == {new_data} failed"
                    elif read_new_data_a and not read_new_data_b:
                        assert self.data_out_b == new_old_data, f"{self.data_out_b} == {new_old_data} failed"
                        assert self.data_out_a == new_data, f"{self.data_out_a} == {new_data} failed"
                    else:
                        assert self.data_out_b == new_old_data, f"{self.data_out_b} == {new_old_data} failed"
                        assert self.data_out_a == new_old_data, f"{self.data_out_a} == {new_data} failed"
                new_data = data
                new_old_data = old_data

    if mode == "rtl":
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(Top, "test_simple_dual_port_ram_sim")

def test_simple_dual_port_ram_sim_TT(mode: str = "sim"):
    test_simple_dual_port_ram_sim(mode, read_new_data_a=True, read_new_data_b=True)

def test_simple_dual_port_ram_sim_TF(mode: str = "sim"):
    test_simple_dual_port_ram_sim(mode, read_new_data_a=True, read_new_data_b=False)

def test_simple_dual_port_ram_sim_FT(mode: str = "sim"):
    test_simple_dual_port_ram_sim(mode, read_new_data_a=False, read_new_data_b=True)

def test_simple_dual_port_ram_sim_FF(mode: str = "sim"):
    test_simple_dual_port_ram_sim(mode, read_new_data_a=False, read_new_data_b=False)

class Pixel(Struct):
    r = Unsigned(8)
    g = Unsigned(8)
    b = Unsigned(8)

def test_struct_ram(mode: str = "rtl", registered_input: bool = True, registered_output: bool = False):
    class Top(Module):
        data_in = Input(Pixel)
        data_out = Output(Pixel)
        addr = Input(Unsigned(8))
        write_en = Input(logic)
        clk = ClkPort()

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
            mem.write_en <<= self.write_en

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
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(Top, "_test_single_port_ram")




def test_basic_simple():
    class Top(Module):
        do_log = True

        def body(self):
            self.data_in = Wire(Unsigned(8))
            self.data_out = Wire(Unsigned(8))
            self.addr = Wire(Unsigned(7))
            self.write_en = Wire(logic)
            self.write_clk = Wire(logic)

            self.reg_data = Reg(self.data_out, clock_port=self.write_clk)
            mem = _BasicMemory(port_cnt=1)
            mem.do_log = True
            mem.set_port_type(0, Unsigned(8))
            mem.data_in_0_port <<= self.data_in
            self.data_out <<= mem.data_out_0_port
            mem.addr_0_port <<= self.addr
            mem.write_en_0_port <<= self.write_en
            mem.write_clk_0_port <<= self.write_clk

        def simulate(self, simulator):
            self.write_en <<= 1
            self.write_clk <<= 0
            yield 10
            for i in range(10):
                self.data_in <<= i
                self.addr <<= i
                self.write_clk <<= 1
                yield 5
                self.write_clk <<= 0
                yield 5
                assert self.data_out == i
            if self.do_log: simulator.log("================================")
            for i in range(10):
                self.data_in <<= i+100
                self.addr <<= i
                # We need two ordering delays here.
                # The first one lets the read happen, while the second one allows the input to Reg to settle before the clock-edge.
                # With only one, the data and the clock would change at the same time and the Reg would (rightly so) set its output to None.
                # NOTE: while read is asynchronous, it still takes time. The value update from the read happens, and *has to* happen
                #       one delta after the address change.
                yield 0
                yield 0
                self.write_clk <<= 1
                yield 5
                self.write_clk <<= 0
                yield 5
                assert self.data_out == i+100
                assert self.reg_data == i

    Build.simulation(Top, "test_simple.vcd", add_unnamed_scopes=True)


def test_basic_dual_port():
    class Top(Module):
        def body(self):
            self.data_in_1 = Wire(Unsigned(8))
            self.data_out_1 = Wire(Unsigned(8))
            self.addr_1 = Wire(Unsigned(7))
            self.write_en_1 = Wire(logic)
            self.write_clk_1 = Wire(logic)

            self.data_in_2 = Wire(Unsigned(8))
            self.data_out_2 = Wire(Unsigned(8))
            self.addr_2 = Wire(Unsigned(7))
            self.write_en_2 = Wire(logic)
            self.write_clk_2 = Wire(logic)

            self.reg_data_1 = Reg(self.data_out_1, clock_port=self.write_clk_2)
            self.reg_data_2 = Reg(self.data_out_2, clock_port=self.write_clk_2)

            mem = _BasicMemory(port_cnt=2)
            mem.do_log = True
            mem.set_port_type(0, Unsigned(8))
            mem.set_port_type(1, Unsigned(8))

            mem.data_in_0_port <<= self.data_in_1
            self.data_out_1 <<= mem.data_out_0_port
            mem.addr_0_port <<= self.addr_1
            mem.write_en_0_port <<= self.write_en_1
            mem.write_clk_0_port <<= self.write_clk_1

            mem.data_in_1_port <<= self.data_in_2
            self.data_out_2 <<= mem.data_out_1_port
            mem.addr_1_port <<= self.addr_2
            mem.write_en_1_port <<= self.write_en_2
            mem.write_clk_1_port <<= self.write_clk_2

        def simulate(self, simulator):
            self.write_en_1 <<= 1
            self.write_en_2 <<= 1
            self.write_clk_1 <<= 0
            self.write_clk_2 <<= 0
            yield 10
            for i in range(10):
                self.data_in_1 <<= i
                self.addr_1 <<= i
                self.addr_2 <<= i
                self.write_clk_1 <<= 1
                yield 5
                self.write_clk_1 <<= 0
                yield 5
                assert self.data_out_1 == i
                assert self.data_out_2 == i
            simulator.log("================================")
            for i in range(10):
                self.data_in_2 <<= i+100
                self.addr_1 <<= i
                self.addr_2 <<= i
                # We need two ordering delays here.
                # The first one lets the read happen, while the second one allows the input to Reg to settle before the clock-edge.
                # With only one, the data and the clock would change at the same time and the Reg would (rightly so) set its output to None.
                # NOTE: while read is asynchronous, it still takes time. The value update from the read happens, and *has to* happen
                #       one delta after the address change.
                yield 0
                yield 0
                self.write_clk_2 <<= 1
                yield 5
                self.write_clk_2 <<= 0
                yield 5
                assert self.data_out_1 == i+100
                assert self.reg_data_1 == i
                assert self.data_out_2 == i+100
                assert self.reg_data_2 == i

    Build.simulation(Top, "test_dual_port.vcd", add_unnamed_scopes=True)


def test_basic_dual_size():
    class Top(Module):
        def body(self):
            self.data_in_1 = Wire(Unsigned(8))
            self.data_out_1 = Wire(Unsigned(8))
            self.addr_1 = Wire(Unsigned(7))
            self.write_en_1 = Wire(logic)
            self.write_clk_1 = Wire(logic)

            self.data_in_2 = Wire(Unsigned(16))
            self.data_out_2 = Wire(Unsigned(16))
            self.addr_2 = Wire(Unsigned(6))
            self.write_en_2 = Wire(logic)
            self.write_clk_2 = Wire(logic)

            mem = _BasicMemory(port_cnt=2)
            mem.set_port_type(0, Unsigned(8))
            mem.set_port_type(1, Unsigned(16))
            mem.do_log = True

            mem.data_in_0_port <<= self.data_in_1
            self.data_out_1 <<= mem.data_out_0_port
            mem.addr_0_port <<= self.addr_1
            mem.write_en_0_port <<= self.write_en_1
            mem.write_clk_0_port <<= self.write_clk_1

            mem.data_in_1_port <<= self.data_in_2
            self.data_out_2 <<= mem.data_out_1_port
            mem.addr_1_port <<= self.addr_2
            mem.write_en_1_port <<= self.write_en_2
            mem.write_clk_1_port <<= self.write_clk_2

        def simulate(self, simulator):
            self.write_en_1 <<= 1
            self.write_en_2 <<= 1
            self.write_clk_1 <<= 0
            self.write_clk_2 <<= 0
            yield 10
            # Write on narrow port
            for i in range(10):
                self.data_in_1 <<= i
                self.addr_1 <<= i
                self.addr_2 <<= i // 2
                self.write_clk_1 <<= 1
                yield 5
                self.write_clk_1 <<= 0
                yield 5
                assert self.data_out_1 == i
                if i % 2 == 1:
                    assert self.data_out_2 == i << 8 | (i - 1)

            simulator.log("==========================")
            # Write on wide port
            for i in range(10):
                self.addr_1 <<= i
                if i % 2 == 0:
                    self.data_in_2 <<= (i + 100) | ((i + 101) << 8)
                    self.addr_2 <<= i // 2
                    self.write_clk_2 <<= 1
                    yield 5
                    self.write_clk_2 <<= 0
                    yield 5
                else:
                    yield 10
                assert self.data_out_1 == i + 100
                if i % 2 == 1:
                    assert self.data_out_2 == (i + 100) << 8 | (i + 99)

    Build.simulation(Top, "test_dual_size.vcd", add_unnamed_scopes=True)


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
    #test_simple_dual_port_ram_ftft("rtl")
    #_test_simple_dual_port_ram("rtl", False, True, True, False, READ, WRITE)
    #test_simple_dual_port_ram_ffff("rtl")
    #test_simple_dual_port_ram_tftt("rtl")
    #test_simple_dual_port_ram_tttf("rtl")
    #test_simple_dual_port_ram_tttt("rtl")
    #test_single_port_async_rom("rtl")
    test_simple_dual_port_ram_rw("rtl")
    #test_simple_dual_port_ram_sim()
    #test_single_port_ram_tt("sim")
    #test_struct_ram("rtl")
    #test_simple_dual_port_ram_tftf()
    #test_simple_dual_port_ram_sim("sim", read_new_data_a=True, read_new_data_b=False)
    #test_simple_dual_port_ram_sim("rtl", read_new_data_b=True)
