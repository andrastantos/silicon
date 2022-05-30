#!/usr/bin/python3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".." / ".."))
sys.path.append(str(Path(__file__).parent / ".." / ".." / "unit_tests"))

from typing import *

from silicon import *
from test_utils import *
import inspect

TByte = Unsigned(length=8)

class OneHotDecode(Module):
    input_port = Input(Unsigned(length=2))
    output_port = Output(Unsigned(length=4))

    def body(self):
        self.output_port[0] = self.input_port == 0
        self.output_port[1] = self.input_port == 1
        self.output_port[2] = self.input_port == 2
        self.output_port[3] = self.input_port == 3

class intel_8255(Module):
    rst = RstPort()
    clk = ClkPort()

    n_rd = Input(logic)
    n_wr = Input(logic)
    n_cs = Input(logic)
    addr = Input(Unsigned(length=2))
    data_in = Input(TByte)
    data_out = Output(TByte)
    pa_in = Input(TByte)
    pa_out = Output(TByte)
    pa_out_valid = Output(logic)
    pb_in = Input(TByte)
    pb_out = Output(TByte)
    pb_out_valid = Output(logic)
    pc_in = Input(TByte)
    pc_out = Output(TByte)
    pcl_out_valid = Output(logic)
    pch_out_valid = Output(logic)

    def body(self):
        reg_a = Wire(TByte)
        reg_b = Wire(TByte)
        reg_cl = Wire(Unsigned(length=4))
        reg_ch = Wire(Unsigned(length=4))
        ctrl = Wire(Unsigned(length=7))

        decode = OneHotDecode(self.addr)
        pa_sel = decode[0]
        pb_sel = decode[1]
        pc_sel = decode[2]
        cw_sel = decode[3] & self.data_in[7]
        pc_bit_sel = decode[3] & ~self.data_in[7]

        pcl_i_not_o = ctrl[0]
        pb_i_not_o = ctrl[1]
        group_b_mode = ctrl[2]
        pch_i_not_o = ctrl[3]
        pa_i_not_o = ctrl[4]
        group_a_mode = ctrl[6:5]

        self.pa_out_valid = ~pa_i_not_o
        self.pb_out_valid = ~pb_i_not_o
        self.pcl_out_valid = ~pcl_i_not_o
        self.pch_out_valid = ~pch_i_not_o

        direct_pcl_i_not_o = self.data_in[0]
        direct_pb_i_not_o = self.data_in[1]
        direct_pch_i_not_o = self.data_in[3]
        direct_pa_i_not_o = self.data_in[4]

        wr = ~self.n_cs & ~self.n_wr
        rd = ~self.n_cs & ~self.n_rd
        cw_wr = cw_sel & wr
        pc_bit_sel_wr = pc_bit_sel & wr
        pa_wr = pa_sel & wr
        pb_wr = pb_sel & wr
        pc_wr = pc_sel & wr

        ctrl <<= Reg(Select(cw_wr, ctrl, self.data_in[6:0]), reset_value_port=0x1b)
        reg_a <<= Reg(Select(cw_wr & ~direct_pa_i_not_o & pa_i_not_o, Select(pa_i_not_o, Select(pa_wr, reg_a, self.data_in), self.pa_in), 0))
        reg_b <<= Reg(Select(cw_wr & ~direct_pb_i_not_o & pb_i_not_o, Select(pb_i_not_o, Select(pb_wr, reg_b, self.data_in), self.pb_in), 0))

        # For port C we'll have to work a litte harder. First, it has two nibbles with independent direction control, and second, it supports bit-set/reset functionality
        reg_c_bit = 1 << self.data_in[2:1]
        reg_c_nibble = self.data_in[3]
        reg_c_s_not_r = self.data_in[0]
        reg_cl_bit_change = Select(reg_c_s_not_r, reg_cl & ~reg_c_bit, reg_cl | reg_c_bit)
        reg_ch_bit_change = Select(reg_c_s_not_r, reg_ch & ~reg_c_bit, reg_ch | reg_c_bit)
        reg_cl_update = Select(pc_bit_sel_wr & ~reg_c_nibble, reg_cl, reg_cl_bit_change)
        reg_ch_update = Select(pc_bit_sel_wr &  reg_c_nibble, reg_ch, reg_ch_bit_change)
        reg_cl <<= Reg(Select(cw_wr & ~direct_pcl_i_not_o & pcl_i_not_o, Select(pcl_i_not_o, Select(pc_wr, reg_cl_update, self.data_in[3:0]), self.pc_in[3:0]), 0))
        reg_ch <<= Reg(Select(cw_wr & ~direct_pch_i_not_o & pch_i_not_o, Select(pch_i_not_o, Select(pc_wr, reg_ch_update, self.data_in[7:4]), self.pc_in[7:4]), 0))

        self.pa_out = reg_a
        self.pb_out = reg_b
        self.pc_out = (reg_ch, reg_cl)

        self.data_out = SelectOne(
            pa_sel & ~self.n_cs & ~self.n_rd, reg_a,
            pb_sel & ~self.n_cs & ~self.n_rd, reg_b,
            pc_sel & ~self.n_cs & ~self.n_rd, (reg_ch, reg_cl),
            #(cw_sel | pc_bit_sel) & ~self.n_cs & ~self.n_rd, (ConstantModule(logic, 0), ctrl) # For reads, always return ctrl word, independent of data_in[7] as that was not available on the bi-directional data-bus of the original design.
            (cw_sel | pc_bit_sel) & ~self.n_cs & ~self.n_rd, concat("1'b1", ctrl) # For reads, always return ctrl word, independent of data_in[7] as that was not available on the bi-directional data-bus of the original design.
        )

def test_verilog():
    test.rtl_generation(intel_8255, "intel_8255")

def test_sim():
    class intel_8255_tb(intel_8255):
        def simulate(self) -> TSimEvent:
            def clk() -> int:
                yield 10
                self.clk = ~self.clk
                yield 0
                yield 10
                self.clk = ~self.clk
                yield 0

            print("Simulation started")
            self.rst = 1
            self.clk = 1
            yield 10
            for i in range(5):
                yield from clk()
            self.n_cs = 1
            self.n_rd = 1
            self.n_wr = 1
            self.data_in = 0
            self.addr = 0
            self.pa_in = 0x12
            self.pb_in = 0x34
            self.pc_in = 0x56
            yield from clk()
            self.rst = 0
            for i in range(5):
                yield from clk()

            def read(addr: int) -> Optional[int]:
                self.n_cs = 0
                self.n_rd = 0
                self.n_wr = 1
                self.addr = addr
                yield from clk()
                self.n_cs = 1
                self.n_rd = 1
                self.n_wr = 1
                print("r", end="", flush=True)
                return self.data_out.sim_value
            def write(addr:int, data:int) -> None:
                self.n_cs = 0
                self.n_rd = 1
                self.n_wr = 0
                self.addr = addr
                self.data_in = data
                yield from clk()
                self.n_cs = 1
                self.n_rd = 1
                self.n_wr = 1
                print("w", end="", flush=True)

            assert self.pa_out_valid == 0
            assert self.pb_out_valid == 0
            assert self.pcl_out_valid == 0
            assert self.pch_out_valid == 0
            pa_addr = 0
            pb_addr = 1
            pc_addr = 2
            cw_addr = 3
            data = yield from read(pa_addr)
            assert data == 0x12
            yield from clk()
            data = yield from read(pb_addr)
            assert data == 0x34
            data = yield from read(pc_addr)
            assert data == 0x56
            data = yield from read(cw_addr)
            assert data == 0x9b
            now = yield from clk()

            yield from write(pa_addr, 0x22)
            yield from write(pb_addr, 0x33)
            yield from write(pc_addr, 0x44)
            yield from clk()
            data = yield from read(pb_addr)
            assert data == 0x34
            data = yield from read(pc_addr)
            assert data == 0x56
            data = yield from read(cw_addr)
            assert data == 0x9b

            yield from write(cw_addr, 0b1000_1011) #setting port A to output
            yield from clk()
            assert self.pa_out == 0x00
            assert self.pa_out_valid == 1
            assert self.pb_out_valid == 0
            assert self.pcl_out_valid == 0
            assert self.pch_out_valid == 0
            data = yield from read(pa_addr)
            assert data == 0x00
            yield from write(pa_addr, 0xfe)
            data = yield from read(pa_addr)
            assert data == 0xfe
            assert self.pa_out == 0xfe

            yield from write(cw_addr, 0b1000_1001) #setting port B to output
            yield from clk()
            assert self.pb_out == 0x00
            assert self.pa_out_valid == 1
            assert self.pb_out_valid == 1
            assert self.pcl_out_valid == 0
            assert self.pch_out_valid == 0
            data = yield from read(pb_addr)
            assert data == 0x00
            yield from write(pb_addr, 0xdc)
            data = yield from read(pb_addr)
            assert data == 0xdc
            assert self.pb_out == 0xdc
            data = yield from read(pa_addr)
            assert data == 0xfe
            assert self.pa_out == 0xfe

            yield from write(cw_addr, 0b1000_1000) #setting port CL to output
            yield from clk()
            assert self.pc_out & 15 == 0x0
            assert self.pa_out_valid == 1
            assert self.pb_out_valid == 1
            assert self.pcl_out_valid == 1
            assert self.pch_out_valid == 0
            data = yield from read(pc_addr)
            assert data == 0x50
            yield from write(pc_addr, 0xba)
            data = yield from read(pc_addr)
            assert data == 0x5a
            assert self.pc_out & 15 == 0xa
            data = yield from read(pa_addr)
            assert data == 0xfe
            assert self.pa_out == 0xfe
            data = yield from read(pb_addr)
            assert data == 0xdc
            assert self.pb_out == 0xdc

            yield from write(cw_addr, 0b1000_0000) #setting port CH to output
            yield from clk()
            assert self.pc_out == 0x0a
            assert self.pa_out_valid == 1
            assert self.pb_out_valid == 1
            assert self.pcl_out_valid == 1
            assert self.pch_out_valid == 1
            data = yield from read(pc_addr)
            assert data == 0x0a
            yield from write(pc_addr, 0xb9)
            data = yield from read(pc_addr)
            assert data == 0xb9
            assert self.pc_out == 0xb9
            data = yield from read(pa_addr)
            assert data == 0xfe
            assert self.pa_out == 0xfe
            data = yield from read(pb_addr)
            assert data == 0xdc
            assert self.pb_out == 0xdc

            base_pc = 0xb9
            for i in range(2):
                for j in range(5):
                    yield from clk()

                for bit in range(8):
                    yield from write(cw_addr, bit << 1 | 1) # Set bit
                    base_pc = base_pc | (1 << bit)
                    data = yield from read(pc_addr)
                    assert data == base_pc
                    assert self.pc_out == base_pc

                    yield from write(cw_addr, bit << 1 | 0) # Reset bit
                    base_pc = base_pc & ~(1 << bit)
                    data = yield from read(pc_addr)
                    assert data == base_pc
                    assert self.pc_out == base_pc

            print(f"Done at {now}")

    test.simulation(intel_8255_tb, inspect.currentframe().f_code.co_name)

if __name__ == "__main__":
    test_sim()

"""
An idea from PyRTL: use <<= as the 'bind' operator. Could re-use the same for simulation assignment, though that's ugly. (not that the current hack isn't either)

Alternatives:
    PyRTL - https://ucsbarchlab.github.io/PyRTL/
    pyverilog - https://pypi.org/project/pyverilog/ <-- actually, no, this is a Verilog parser and co. in Python.
    pyMTL - https://github.com/cornell-brg/pymtl
    myHDL - http://www.myhdl.org/

    All of them seem to take the road of trying to understand and convert python to RTL as opposed to 'describe' RTL in python.
"""