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

"""
Memory interface notes:

The original memory interface of the Z80 had some strange timings (half-cycle updates and what not),
but when adjusted for those peculiarities, it is almost exactly like an APB master.

Because of that, this memory interface is simply an APB compliant master with a few extra (address-like)
lines for 'refresh', 'io access' and 'm1'.

"""

'''
RegEn = Reg
'''

class Z80MemIf(Module):
    clk = Input(logic)
    clk_en = Input(logic)
    rst = Input(logic)

    # Interface to the memory
    paddr   = Output(Unsigned(16))
    pm1     = Output(logic)
    prfsh   = Output(logic)
    pio     = Output(logic)
    pwrite  = Output(logic)
    psel    = Output(logic)
    penable = Output(logic)
    pwdata  = Output(TByte)
    prdata  = Input(TByte)
    pready  = Input(logic)

    # Internal control interface
    addr        = Input(Unsigned(16))
    m1          = Input(logic)
    rfsh        = Input(logic)
    io_not_mem  = Input(logic)
    data_out    = Input(TByte)
    data_in     = Output(TByte)
    wr_not_rd   = Input(logic)
    start       = Input(logic)
    done        = Output(logic)
    busy        = Output(logic)

    def body(self):
        self.addr_reg = Wire(Unsigned(16))
        self.m1_reg = Wire(logic)
        self.rfsh_reg = Wire(logic)
        self.io_not_mem_reg = Wire(logic)
        self.wr_not_rd_reg = Wire(logic)
        self.data_out_reg = Wire(TByte)

        self.addr_reg       <<= RegEn(Select(self.start, self.addr_reg      , self.addr))
        self.m1_reg         <<= RegEn(Select(self.start, self.m1_reg        , self.m1))
        self.rfsh_reg       <<= RegEn(Select(self.start, self.rfsh_reg      , self.rfsh))
        self.io_not_mem_reg <<= RegEn(Select(self.start, self.io_not_mem_reg, self.io_not_mem))
        self.wr_not_rd_reg  <<= RegEn(Select(self.start, self.wr_not_rd_reg , self.wr_not_rd))
        self.data_out_reg   <<= RegEn(Select(self.start, self.data_out_reg  , self.data_out))

        phase_idle = 0
        phase_addr = 1
        phase_data = 2

        self.phase = Wire(Unsigned(2))
        self.phase_next = Wire(Unsigned(2))

        self.phase_next <<= Select(self.phase,
            self.start, # IDLE
            phase_data, # ADDR
            Select(self.pready, phase_data, self.start) # DATA
        )
        self.phase <<= RegEn(self.phase_next)

        self.paddr   <<= Select(self.phase == phase_idle, self.addr_reg, self.addr)
        self.pm1     <<= Select(self.phase == phase_idle, self.m1_reg, self.m1)
        self.prfsh   <<= Select(self.phase == phase_idle, self.rfsh_reg, self.rfsh)
        self.pio     <<= Select(self.phase == phase_idle, self.io_not_mem_reg, self.io_not_mem)

        self.pwrite  <<= Select(self.phase == phase_idle, self.wr_not_rd_reg, self.wr_not_rd)
        self.psel    <<= self.phase != phase_idle
        self.penable <<= self.phase == phase_data

        self.pwdata  <<= Select(self.phase == phase_idle, self.data_out_reg, self.data_out)

        self.done <<= (self.phase == phase_data) & self.pready
        self.busy <<= self.phase_next != phase_idle

        self.data_in <<= self.prdata

def test_verilog():
    test.rtl_generation(Z80MemIf, "z80_mem_if")

def test_sim():
    class PDBSlave(Module):
        clk = Input(logic)
        clk_en = Input(logic)
        rst = Input(logic)

        paddr   = Input(Unsigned(16))
        pm1     = Input(logic)
        prfsh   = Input(logic)
        pio     = Input(logic)
        pwrite  = Input(logic)
        psel    = Input(logic)
        penable = Input(logic)
        pwdata  = Input(TByte)
        prdata  = Output(TByte)
        pready  = Output(logic)

        def simulate(self) -> TSimEvent:
            while True:
                yield self.clk, self.penable
                self.pready <<= self.penable     if (self.psel == 1) else None
                if self.clk_en and self.clk.get_sim_edge() == EdgeType.Positive:
                    #self.prdata <<= self.paddr[7:0]  if (self.penable == 1) else None
                    self.prdata <<= self.paddr[7:0]

    class Z80MemIf_tb(Module):
        def body(self) -> None:

            self.clk    = Wire(logic)
            self.clk_en = Wire(logic)
            self.rst    = Wire(logic)

            # Interface to the memory
            self.paddr   = Wire(Unsigned(16))
            self.pm1     = Wire(logic)
            self.prfsh   = Wire(logic)
            self.pio     = Wire(logic)
            self.pwrite  = Wire(logic)
            self.psel    = Wire(logic)
            self.penable = Wire(logic)
            self.pwdata  = Wire(TByte)
            self.prdata  = Wire(TByte)
            self.pready  = Wire(logic)

            # Internal control interface
            self.addr        = Wire(Unsigned(16))
            self.m1          = Wire(logic)
            self.rfsh        = Wire(logic)
            self.io_not_mem  = Wire(logic)
            self.data_out    = Wire(TByte)
            self.data_in     = Wire(TByte)
            self.wr_not_rd   = Wire(logic)
            self.start       = Wire(logic)
            self.done        = Wire(logic)
            self.busy        = Wire(logic)

            uut = Z80MemIf()
            mem_model = PDBSlave()
            for port_name, port in uut.get_ports().items():
                if is_input_port(port):
                    port <<= self.get_wires()[port_name]
                else:
                    self.get_wires()[port_name] <<= port

            for port_name, port in mem_model.get_ports().items():
                if is_input_port(port):
                    port <<= self.get_wires()[port_name]
                else:
                    self.get_wires()[port_name] <<= port

            '''
            uut.clk <<= self.clk
            uut.clk_en <<= self.clk_en
            uut.rst <<= self.rst
            uut.paddr <<= self.paddr
            uut.prfsh <<= self.prfsh
            uut.pio <<= self.pio
            uut.pwrite <<= self.pwrite
            uut.psel <<= self.psel
            uut.penable <<= self.penable
            uut.pwdata <<= self.pwdata
            uut.prdata <<= self.prdata
            uut.pready <<= self.pready
            '''

        def simulate(self) -> TSimEvent:
            # NOTE: we're going to use rdXX register addresses for both reads and writes
            def clk() -> int:
                yield 10
                self.clk <<= ~self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0

            def read(addr, m1, rfsh, io, data, wait_cnt = 0):
                self.addr  <<= addr
                self.m1    <<= m1
                self.rfsh  <<= rfsh
                self.io_not_mem    <<= io
                self.start <<= 1
                if self.busy:
                    while not self.done:
                        yield from clk()
                # The bus cycle should start here
                #assert self.busy == 1

                #assert self.pwrite == 0
                #assert self.psel == 1
                #assert self.paddr == addr
                #assert self.penable == 0

                yield from clk()

                self.addr  <<= None
                self.m1    <<= None
                self.rfsh  <<= None
                self.io_not_mem    <<= None
                self.start <<= 0

                #assert self.pwrite == 0
                #assert self.psel == 1
                #assert self.paddr == addr
                #assert self.penable == 1

                while wait_cnt > 0:
                    #assert self.pwrite == 0
                    #assert self.psel == 1
                    #assert self.paddr == addr
                    #assert self.penable == 1
                    wait_cnt -= 1
                    yield from clk()

                yield from clk()
                #assert self.done
                #assert self.data_in == data

            print("Simulation started")
            self.clk_en <<= 1

            self.rst <<= 1
            self.clk <<= 1
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0
            self.start <<= 0

            for i in range(5):
                yield from clk()

            yield from read(0x1234, 0, 0, 0, 0x56, 0)

            for i in range(5):
                yield from clk()

            print(f"Done")

    test.simulation(Z80MemIf_tb, "z80_mem_if")

if __name__ == "__main__":
    test_sim()
    #test_verilog()
