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

class mc6845(Module):
    rst = Input(logic)
    clk = Input(logic)

    pclk_en = Input(logic)

    n_wr = Input(logic)
    bus_en = Input(logic)
    n_cs = Input(logic)
    addr = Input(logic)
    data_in = Input(TByte)
    data_out = Output(TByte)

    n_lpstb = Input(logic) # Light pen strobe
    de = Output(logic) # Display enable
    hs = Output(logic) # Horizontal sync
    vs = Output(logic) # Vertical synx

    ma = Output(Unsigned(length=14)) # Memory address
    ra = Output(Unsigned(length=5)) # Row address

    cursor = Output(logic)

    def body(self):
        # Constants
        v_sync_width = 5 # Should be 15 in rality

        # Register file
        self.r0_horizontal_total = Wire(TByte)
        self.r1_horizontal_displayed = Wire(TByte)
        self.r2_horizontal_sync_pos = Wire(TByte)
        self.r3_sync_width = Wire(Unsigned(length=4))
        self.r4_vertical_total = Wire(Unsigned(length=7))
        self.r5_vertical_total_adjust = Wire(Unsigned(length=5))
        self.r6_vertical_displayed = Wire(Unsigned(length=7))
        self.r7_vertical_sync_pos = Wire(Unsigned(length=7))
        self.r8_interlace_and_skew = Wire(Unsigned(length=2))
        self.r9_max_scan_line_addr = Wire(Unsigned(length=5))
        self.r10_cursor_start = Wire(Unsigned(length=7))
        self.r11_cursor_end = Wire(Unsigned(length=5))
        r12_start_addr = Wire(Unsigned(length=6))
        r13_start_addr = Wire(TByte)
        r14_cursor = Wire(Unsigned(length=6))
        r15_cursor = Wire(TByte)
        #self.r12_r13_start_addr = Wire(Unsigned(length=14))
        #self.r14_r15_cursor = Wire(Unsigned(length=14))
        self.r12_r13_start_addr = Concatenator(r12_start_addr, r13_start_addr)
        self.r14_r15_cursor = Concatenator(r14_cursor, r15_cursor)
        self.r16_r17_light_pen = Wire(Unsigned(length=14))

        # Bus interface
        wr_idx = ~self.n_cs & ~self.addr & ~self.n_wr & self.bus_en
        wr_reg = ~self.n_cs & self.addr & ~self.n_wr & self.bus_en

        reg_idx = Wire(Unsigned(length=5))
        reg_idx <<= Reg(Select(wr_idx, reg_idx, self.data_in[4:0]))
        self.r0_horizontal_total      <<= Reg(Select(wr_reg & (reg_idx == 0), self.r0_horizontal_total, self.data_in))
        self.r1_horizontal_displayed  <<= Reg(Select(wr_reg & (reg_idx == 1), self.r1_horizontal_displayed, self.data_in))
        self.r2_horizontal_sync_pos   <<= Reg(Select(wr_reg & (reg_idx == 2), self.r2_horizontal_sync_pos, self.data_in))
        self.r3_sync_width            <<= Reg(Select(wr_reg & (reg_idx == 3), self.r3_sync_width, self.data_in[3:0]))
        self.r4_vertical_total        <<= Reg(Select(wr_reg & (reg_idx == 4), self.r4_vertical_total, self.data_in[6:0]))
        self.r5_vertical_total_adjust <<= Reg(Select(wr_reg & (reg_idx == 5), self.r5_vertical_total_adjust, self.data_in[4:0]))
        self.r6_vertical_displayed    <<= Reg(Select(wr_reg & (reg_idx == 6), self.r6_vertical_displayed, self.data_in[6:0]))
        self.r7_vertical_sync_pos     <<= Reg(Select(wr_reg & (reg_idx == 7), self.r7_vertical_sync_pos, self.data_in[6:0]))
        self.r8_interlace_and_skew    <<= Reg(Select(wr_reg & (reg_idx == 8), self.r8_interlace_and_skew, self.data_in[1:0]))
        self.r9_max_scan_line_addr    <<= Reg(Select(wr_reg & (reg_idx == 9), self.r9_max_scan_line_addr, self.data_in[4:0]))
        self.r10_cursor_start         <<= Reg(Select(wr_reg & (reg_idx == 10), self.r10_cursor_start, self.data_in[6:0]))
        self.r11_cursor_end           <<= Reg(Select(wr_reg & (reg_idx == 11), self.r11_cursor_end, self.data_in[4:0]))
        #self.r12_r13_start_addr[13:8] <<= Reg(Select(wr_reg & (reg_idx == 12), self.r12_r13_start_addr, self.data_in[5:0]))
        #self.r12_r13_start_addr[7:0]  <<= Reg(Select(wr_reg & (reg_idx == 13), self.r12_r13_start_addr, self.data_in))
        #self.r14_r15_cursor[13:8]     <<= Reg(Select(wr_reg & (reg_idx == 14), self.r14_r15_cursor, self.data_in[5:0]))
        #self.r14_r15_cursor[7:0]      <<= Reg(Select(wr_reg & (reg_idx == 15), self.r14_r15_cursor, self.data_in))
        r12_start_addr                <<= Reg(Select(wr_reg & (reg_idx == 12), r12_start_addr, self.data_in[5:0]))
        r13_start_addr                <<= Reg(Select(wr_reg & (reg_idx == 13), r13_start_addr, self.data_in))
        r14_cursor                    <<= Reg(Select(wr_reg & (reg_idx == 14), r14_cursor, self.data_in[5:0]))
        r15_cursor                    <<= Reg(Select(wr_reg & (reg_idx == 15), r15_cursor, self.data_in))
        
        # On some variants of the chip, there is a status register. For now, we're going to leave that out
        #stat_reg = Wire(TByte)
        stat_reg = 0
        # Most registers are write-only
        self.data_out = Select(self.addr, stat_reg, Select(reg_idx, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, self.r14_r15_cursor[13:8], self.r14_r15_cursor[7:0], self.r16_r17_light_pen[13:8], self.r16_r17_light_pen[7:0]))

        # TODO: what to do with the difference between bus-clock and character-clock?
        # In the CPC6128 the CCLK is 1MHz, while the CPU clock is 4MHz. The oscillator is running at 16MHz. nCPU also seems to be a 1MHz clock, which also drives the audio chip. nCPU drives the address muxes, so 
        # out of the 4MHz pulses 2 is given to the CPU and 2 to the CRTC. Given that during this time the DRAM RAS/CAS sequencing also needs to take place (using another ULA-generated signal), chances are these
        # two cycles are simply used to generate the RAS/CAS access. The 'E' or 'bus_en' pin is driven by ~(nIORD & nIOWR) so that's not really a clock in the system.
        # Overall, I think it's common that the character clock is some multiple of the bus clock, so a clock-enable should suffice, but can we take that as a design constraint? For now, probably.
        # There seems to be some shananigans going on to get 80-column mode going, where CCLK is part of the address. That allows - if timed right - to read two bytes (16 bits) for each character from memory.
        # but that requires that DRAM actually gets 8 CAS/RAS timeslots? The two 1MHz clocks in the system are indeed out of phase from one another.
        # It appears that it's best to keep one clock and two clock-enables around: one for the bus, one for the character clock.
        #
        # So, here's what I'm going to do:
        # I'm goging to stick with a single clock, but there will be a fixed pre-divider before we enter the counters. This is a 4-bit counter, which means that the clock to be fed to this new chip is 16MHz.
        # The pre-divider corresponding to the address counter is exposed, giving us 4 extra bits to be used for addressing. The clock (well, d'uh) is also available externally that can be used to generate
        # the appropriate bus transactions. The pre-divider can also be used to generate the required clock-enable signals.

        # Horizontal timing logic
        h_cnt = Wire(TByte)
        h_sync_cnt = Wire(Unsigned(length=4))

        h_line_end = h_cnt == self.r0_horizontal_total
        next_h_cnt = Select(h_line_end & self.pclk_en, (h_cnt + self.pclk_en)[7:0], 0)
        h_cnt <<= Reg(next_h_cnt)

        h_disp_end = next_h_cnt == self.r1_horizontal_displayed
        h_sync_start = next_h_cnt == self.r2_horizontal_sync_pos
        next_h_sync_cnt = Select(h_sync_start & self.pclk_en, (h_sync_cnt + self.pclk_en)[3:0], 0)
        h_sync_cnt <<= Reg(next_h_sync_cnt)
        h_sync_end = next_h_sync_cnt == self.r3_sync_width
        
        self.hs = Reg(
            Select(self.pclk_en, 
                self.hs,
                Select(h_sync_end, 
                    Select(h_sync_start, self.hs, 1),
                    0
                ),
            )
        )

        h_disp_valid = Wire(logic)
        next_h_disp_valid = Select(self.pclk_en,
            h_disp_valid, 
            Select(h_line_end, 
                Select(h_disp_end, h_disp_valid, 0),
                1
            )
        ),
        h_disp_valid <<= Reg(next_h_disp_valid)

        # Verical timing logic
        # char_* counts character lines (coarser vertical count)
        # scan_line_* counts scan-lines within a character
        vclk_en = h_line_end & self.pclk_en
        vertical_overscan = Wire(logic)

        scan_line_cnt = Wire(Unsigned(length=5))

        scan_line_end = vclk_en & (scan_line_cnt == self.r9_max_scan_line_addr)
        scan_line_overscan_end = vclk_en & (scan_line_cnt == self.r5_vertical_total_adjust)
        scan_line_rst = Select(vertical_overscan, scan_line_end, scan_line_overscan_end)

        next_scan_line_cnt = Select(scan_line_end, (scan_line_cnt + vclk_en)[4:0], 0)
        scan_line_cnt <<= Reg(next_scan_line_cnt)

        cclk_en = scan_line_end

        char_row_cnt = Wire(Unsigned(length=7))
        char_row_end = (char_row_cnt == self.r4_vertical_total) & cclk_en
        overscan_needed = self.r5_vertical_total_adjust != 0
        vertical_overscan <<= Reg(Select(scan_line_overscan_end, Select(char_row_end, vertical_overscan, 1), 0))
        v_end = Select(overscan_needed, char_row_end, vertical_overscan & scan_line_overscan_end)
        next_char_row_cnt = Select(v_end, (char_row_cnt + cclk_en)[6:0], 0)
        char_row_cnt <<= Reg(next_char_row_cnt)

        v_disp_end = (next_char_row_cnt == self.r6_vertical_displayed) & cclk_en
        v_sync_start = (next_char_row_cnt == self.r7_vertical_sync_pos) & cclk_en

        v_disp_valid = Wire(logic)
        next_v_disp_valid = Select(v_end, Select(v_disp_end, v_disp_valid, 0), 1)
        v_disp_valid <<= Reg(next_v_disp_valid)

        v_sync_cnt = Wire(Unsigned(length=4))
        v_sync_cnt <<= Reg(Select(v_sync_start & vclk_en, (v_sync_cnt + vclk_en)[3:0], 0))

        v_sync_end = v_sync_cnt == v_sync_width

        self.vs = Reg(Select(v_sync_start, Select(v_sync_end, self.vs, 0), 1))

        disp_valid = Wire(logic)
        next_disp_valid = Select(self.pclk_en, disp_valid, next_h_disp_valid & next_v_disp_valid)
        disp_valid <<= Reg(next_disp_valid)
        self.de = disp_valid

        # Address generation
        char_addr = Wire(Unsigned(length=14))
        line_start_addr = Wire(Unsigned(length=14))

        next_char_addr = Select( v_end, 
            Select( h_line_end & ~scan_line_end & self.pclk_en, 
                char_addr + (self.pclk_en & disp_valid), 
                line_start_addr
            )[13:0], 
            self.r12_r13_start_addr
        )

        char_addr <<= Reg(next_char_addr)

        line_start_addr <<= Reg(Select(v_end, Select(scan_line_end, line_start_addr, char_addr), self.r12_r13_start_addr))
        self.ma = char_addr
        self.ra = scan_line_cnt

        # Cursor generation
        cursor_blink = self.r10_cursor_start[6]
        cursor_blink_period = self.r10_cursor_start[5]
        cursor_start = self.r10_cursor_start[4:0]
        cursor_end = self.r11_cursor_end

        cursor_rows = Wire(logic)
        field_cnt = Wire(Unsigned(length=5))
        field_cnt <<= Reg((field_cnt + v_end)[4:0])
        cursor_on = Select(cursor_blink, ~cursor_blink_period, Select(cursor_blink_period, field_cnt[3], field_cnt[4]))
        cursor_rows_start = next_scan_line_cnt == cursor_start
        cursor_rows_end = scan_line_cnt == cursor_end
        next_cursor_rows = Select(vclk_en,
            cursor_rows,
            Select(cursor_rows_start, 
                Select(cursor_rows_end,
                    cursor_rows,
                    0
                ),
                1
            )
        )
        cursor_rows <<= Reg(next_cursor_rows)

        cursor_addr_match = Wire(logic)
        next_cursor_addr_match = Select(self.pclk_en, cursor_addr_match, next_char_addr == self.r14_r15_cursor)
        cursor_addr_match <<= Reg(next_cursor_addr_match)
        next_cursor = next_disp_valid & next_cursor_addr_match & cursor_on & next_cursor_rows
        self.cursor = Reg(next_cursor)

        # Light pen
        self.r16_r17_light_pen <<= Reg(Select(self.n_lpstb, char_addr, self.r16_r17_light_pen))

def test_verilog():
    test.rtl_generation(mc6845, "mc6845")

def test_sim():
    class mc6845_tb(mc6845):
        def simulate(self) -> TSimEvent:
            self.pclk_cnt = 0
            def clk() -> int:
                yield 10
                self.clk = ~self.clk
                yield 10
                self.clk = ~self.clk
                yield 0
                self.pclk_cnt += 1
                if self.pclk_cnt == 4:
                    self.pclk_cnt = 0
                    self.pclk_en = 1
                else:
                    self.pclk_en = 0

            print("Simulation started")
            self.rst = 1
            self.clk = 1
            yield 10
            for i in range(5):
                yield from clk()
            self.bus_en = 0
            self.n_cs = 1
            self.n_wr = None
            self.data_in = 0
            self.addr = 0

            self.n_lpstb = 1

            yield from clk()
            self.rst = 0
            for i in range(5):
                yield from clk()
            
            def read(reg_idx: int) -> Optional[int]:
                # Select register by writing to the index
                self.n_cs = 0
                self.n_wr = 0
                self.bus_en = 1
                self.addr = 0
                self.data_in = reg_idx
                yield from clk()
                # Read from data register and return it
                self.n_cs = 0
                self.n_wr = 1
                self.bus_en = 1
                self.addr = 1
                self.data_in = None
                yield from clk()
                self.n_cs = 1
                self.n_wr = None
                self.bus_en = 0
                self.addr = None
                self.data_in = None
                return self.data_out.sim_value

            def write(reg_idx:int, data:int) -> None:
                # Select register by writing to the index
                self.n_cs = 0
                self.n_wr = 0
                self.bus_en = 1
                self.addr = 0
                self.data_in = reg_idx
                yield from clk()
                # Write data into data register
                self.n_cs = 0
                self.n_wr = 0
                self.bus_en = 1
                self.addr = 1
                self.data_in = data
                yield from clk()
                self.n_cs = 1
                self.n_wr = 1
                #self.n_wr = None
                self.bus_en = 0
                #self.addr = None
                #self.data_in = None

            yield from write(0, 14)
            yield from write(1, 5)
            yield from write(2, 7)
            yield from write(3, 3)
            yield from write(4, 10) # 10 character lines per frame
            yield from write(5, 0) # No fractional line at the end (for now)
            yield from write(6, 5) # 5 visible character lines
            yield from write(7, 7)
            yield from write(8, 0) # No interlace
            yield from write(9, 2) # 2 scan-lines per character
            yield from write(10, (0 << 5) | 1) # cursor start (enable cursor)
            yield from write(11, 1) # cursor end
            yield from write(12, 1) # start address high
            yield from write(13, 0) # start address low
            yield from write(14, 1) # cursor address high
            yield from write(15, 0) # cursor address low
            
            print(f"All registers programmed")
            for i in range(1000):
                now = yield from clk()
                if i % 100 == 0:
                    print(".", end="", flush=True)

            print(f"Done at {now}")

    test.simulation(mc6845_tb)

if __name__ == "__main__":
    #test_verilog()
    #import profile as profile
    #profile.run("test_sim()", filename="mc6845.tests", sort='cumtime')
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