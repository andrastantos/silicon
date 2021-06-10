#!/usr/bin/python3
# Good documents https://cpctech.cpc-live.com/docs.html

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".." / ".."))
sys.path.append(str(Path(__file__).parent / ".." / ".." / "unit_tests"))

from typing import *

from silicon import *
from test_utils import *
import inspect

TByte = Unsigned(length=8)

class gate_array(Module):
    rst = Input(logic)
    clk = Input(logic) # 16MHz clock input

    n_m1 = Input(logic) # Low during op-code fetch also low during interrupt vector read (one with mreq the other with iorq)
    n_wr = Input(logic)
    n_rd = Input(logic)
    n_mreq = Input(logic)
    n_iorq = Input(logic)
    pix_en = Input(logic) # Set high when data-bus contains pixel reads (could be derived from timing, but I think it's more logical to keep that external)
    addr = Input(Unsigned(length=2))

    data_in = Input(TByte)

    dispen = Input(logic)
    hsync = Input(logic)
    vsync = Input(logic)

    video_r = Output(Unsigned(length=2))
    video_g = Output(Unsigned(length=2))
    video_b = Output(Unsigned(length=2))
    video_nsync = Output(logic)

    rom_u_en = Output(logic) # Enable ROM in the 0xc000-0xffff region (address-decoded, mem-qualified)
    rom_l_en = Output(logic) # Enable ROM in the 0x0000-0x3fff region (address-decoded, mem-qualified)
    ram_en   = Output(logic) # Enable RAM access in any region
    #n_244_en = Output(logic) # Has something to do with disconnecting the Z80 from the DRAM data-bus (CPU write direction) (probably during CCRT accesses)

    addr_out = Output(Unsigned(length=4)) # Replaces addr[17:14] to provide up to 256kRAM access
    #n_casad = Output(logic) # Something weird about DRAM address muxing. Hopefully not needed.

    n_int = Output(logic) # Generates a Z80 interrupt

    def body(self):
        # Constants
        ##########################################################################################
        hsync_limit = 52

        # Register interface
        ##########################################################################################
        reg_sel = self.addr == 1
        reg_wr = reg_sel & ~self.n_wr & ~self.n_iorq & self.n_rd & ~self.n_m1

        int_ack = ~self.n_m1 & ~self.n_iorq

        # top two data bits decode register
        pen_select = self.data_in[7:6] == 0
        color_select = self.data_in[7:6] == 1
        scr_rom_int_select = self.data_in[7:6] == 2
        ram_page_select = self.data_in[7:6] == 3

        pen_mask = concat(self.data_in[4], ~self.data_in[4], ~self.data_in[4], ~self.data_in[4], ~self.data_in[4])

        # pen register
        self.pen_sel_reg = Wire(Number(min_val = 0, max_val = 16)) # 0...15: pen, 16: border
        self.pen_sel_reg <<= Reg(Select(reg_wr & pen_select, self.pen_sel_reg, self.data_in[4:0] & pen_mask))
        # color palette register array and it's access
        self.pen_colors = []
        for i in range(17):
            self.pen_colors.append(Wire(Unsigned(length=5)))
        for i in range(17):
            self.pen_colors[i] <<= Reg(Select(reg_wr & color_select & self.pen_sel_reg == i, self.pen_colors[i], self.data_in[4:0]))
        # video mode and ROM enable
        self.next_video_mode = Wire(Unsigned(length=2))
        self.video_mode = Wire(Unsigned(length=2))
        self.rom_u_dis = Wire(logic)
        self.rom_l_dis = Wire(logic)

        int_delay = Select(reg_wr & scr_rom_int_select, 0, self.data_in[4])
        self.rom_u_dis <<= Reg(Select(reg_wr & scr_rom_int_select, self.rom_u_dis, self.data_in[3]))
        self.rom_l_dis <<= Reg(Select(reg_wr & scr_rom_int_select, self.rom_l_dis, self.data_in[2]))

        self.next_video_mode <<= Reg(Select(reg_wr & scr_rom_int_select, self.video_mode, self.data_in[1:0]))
        self.video_mode <<= Reg(Select(self.hsync, self.video_mode, self.next_video_mode)) # Video mode changes are synced to HSYNC

        # Address decode for memories and RAM paging logic (paging happens to be no-op for ROMs)
        ##########################################################################################
        # RAM page select (based on http://www.cpctech.org.uk/docs/rampage.html)
        self.secondary_ram_page = Wire(Unsigned(length=2))
        self.ram_config = Wire(Unsigned(length=3))
        self.secondary_ram_page <<= Reg(Select(reg_wr & ram_page_select & self.data_in[5], self.secondary_ram_page, self.data_in[4:3]))
        self.ram_config <<= Reg(Select(reg_wr & ram_page_select, self.ram_config, self.data_in[2:0]))

        page0 = self.addr == 0 & self.n_mreq
        page1 = self.addr == 1 & self.n_mreq
        page2 = self.addr == 2 & self.n_mreq
        page3 = self.addr == 3 & self.n_mreq
        self.rom_u_en <<= ~self.rom_u_dis & page3
        self.rom_l_en <<= ~self.rom_l_dis & page0
        self.ram_en <<= (self.rom_u_dis & page3) | (self.rom_l_dis & page0) | page1 | page2
        high_page0 = Select(self.ram_config, 0,0,1,0,0,0,0,0)
        bank_page0 = 0
        high_page1 = Select(self.ram_config, 0,0,1,0,1,1,1,1)
        bank_page1 = Select(self.ram_config, 1,1,1,3,0,1,2,3)
        high_page2 = Select(self.ram_config, 0,0,1,0,0,0,0,0)
        bank_page2 = 2
        high_page3 = Select(self.ram_config, 0,1,1,1,0,0,0,0)
        bank_page3 = 3
        high_page = Select(self.addr, high_page0, high_page1, high_page2, high_page3)
        bank_page = Select(self.addr, bank_page0, bank_page1, bank_page2, bank_page3)
        self.addr_out <<= concat(Select(high_page, 0, self.secondary_ram_page), bank_page)

        # interrupt generation (based on https://cpctech.cpc-live.com/docs/gaint.html and https://cpctech.cpc-live.com/docs/ints.html)
        ##########################################################################################
        self.hsync_delay_line = Wire(Unsigned(length=2))
        self.hsync_delay_line <<= Reg(concat(self.hsync_delay_line[0], self.hsync))
        hsync_falling_edge = self.hsync_delay_line[1] & ~self.hsync_delay_line[0]
        self.vsync_delay_line = Wire(Unsigned(length=2))
        self.vsync_delay_line <<= Reg(concat(self.vsync_delay_line[0], self.vsync))
        vsync_rising_edge = ~self.vsync_delay_line[1] & self.vsync_delay_line[0]

        self.hsync_cnt = Wire(Unsigned(length=6))
        self.hsync_after_vsync_cnt = Wire(Unsigned(length=2))
        self.hsync_int = Wire(logic)
        hsync_at_limit = self.hsync_cnt == hsync_limit
        # This is complex here. On top of the standard resettable counter on hsync, we have the following logic:
        # - When interrupt is acknowledged, clear MSB to make sure interrupts are not fired closer than 32 scan-lines
        # - If int_delay is set (being written as 1), reset counter
        # - If after the second HSYNC during a VSYNC, the counter is >= 32, interrupt is raised
        # - hsync counter is reset upon second HSYNC during VSYNC
        hsync_after_vsync_start = vsync_rising_edge
        hsync_after_vsync_stop = self.hsync_after_vsync_cnt == 2
        hsync_after_vsync_counting = Wire(logic)
        hsync_after_vsync_counting <<= Reg(Select(hsync_after_vsync_stop, Select(hsync_after_vsync_start, hsync_after_vsync_counting, 1), 0))
        self.hsync_after_vsync_cnt <<= Reg(Select(hsync_after_vsync_counting, 0, (self.hsync_after_vsync_cnt + hsync_falling_edge)[1:0]))

        next_hsync_cnt = Select(int_delay | hsync_after_vsync_stop,
            Select(hsync_falling_edge, 
                self.hsync_cnt, 
                Select(hsync_at_limit, 
                    (self.hsync_cnt + 1)[5:0],
                    0
                )
            ) & concat(~int_ack, "5'b1"),
            0
        )
        self.hsync_cnt <<= Reg(next_hsync_cnt)
        self.hsync_int <<= Reg(Select(int_ack | int_delay, Select(hsync_at_limit | (hsync_after_vsync_stop & next_hsync_cnt[5]), self.hsync_int, 1), 0))
        self.n_int <<= ~self.hsync_int

        # Video interface
        ##########################################################################################
        # https://neuro-sys.github.io/2019/10/01/amstrad-cpc-crtc.html
        # Video modes:
        # Mode 0, 160x200 resolution, 16 colours
        # Mode 1, 320x200 resolution, 4 colours
        # Mode 2, 640x200 resolution, 2 colours
        # Mode 3, 160x200 resolution, 4 colours (note 1)
        self.pixel_prescaler = Wire(Unsigned(length=2))
        pixel_prescaler_limit = Select(self.video_mode, 3, 1, 0, 3)
        pixel_shift_en = self.pixel_prescaler == pixel_prescaler_limit
        self.pixel_prescaler <<= Select(pixel_shift_en, self.pixel_prescaler + 1, 0)
        self.pixel_shift_reg = Wire(TByte)
        pixel_shifter = Select(self.video_mode, self.pixel_shift_reg[7:4], self.pixel_shift_reg[7:2], self.pixel_shift_reg[7:1], self.pixel_shift_reg[7:2])
        self.next_disp_byte_reg = Wire(TByte)
        self.next_disp_byte_reg <<= Reg(Select(self.pix_en, self.next_disp_byte_reg, self.data_in))
        # There's a little trickery here with the loading of the shift-register: theoretically the pixel_shift_en clock and self.pix_en can have arbitrary phase to one another.
        # This means that we might want to delay the loading of the shift register from the data-bus (thus self.next_disp_byte_reg), but only if we really need to. If the phases
        # work out fine, we can directly load from the data-bus.
        # Now, in practice the phase relationships are hard and known ahead of time, but I just don't quite know it at this instant. Also, the sync relationships matter too,
        # otherwise the programmed sync pulses will not be where the should and the screen would shift left/right depending...
        # TODO: something to figure out and fine-tune once the overall system latency is known and the phase relationships can be figured out.
        self.pixel_shift_reg <<= Reg(Select(self.pix_en, Select(pixel_shift_en, self.pixel_shift_reg, pixel_shifter), Select(pixel_shift_en, self.next_disp_byte_reg, self.data_in)))

        pixel_pen = Select(self.dispen, 16, Select(self.video_mode, self.pixel_shift_reg[3:0], self.pixel_shift_reg[1:0], self.pixel_shift_reg[0], self.pixel_shift_reg[1:0]))

        # Look-up pen color from palette
        pixel_color = Select(pixel_pen, *self.pen_colors)

        # HW color to RGB conversion table
        #                                    0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31
        self.video_r <<= Select(pixel_color, 1, 1, 0, 2, 0, 2, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1 ,1, 1, 1, 1, 1)
        self.video_g <<= Select(pixel_color, 1, 1, 2, 2, 0, 0, 1, 1, 0, 2, 2, 2, 0, 0, 1, 1, 0, 2, 2, 2, 0, 0, 1, 1, 0, 2, 2 ,2, 0, 0, 1, 1)
        self.video_b <<= Select(pixel_color, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 2, 0, 2, 0, 2, 1, 1, 0, 2, 0, 2, 0, 2, 1, 1, 0 ,2, 0, 2, 0, 2)
        self.video_nsync <<= ~ (self.vsync | self.hsync)

        ##### Per https://cpctech.cpc-live.com/docs/ints2.html the CPC forces each Z80 instruction to the 1us boundary.

def test_verilog():
    test.rtl_generation(gate_array, "gate_array")

'''
def test_sim():
    class mc6845_tb(mc6845):
        def simulate(self) -> TSimEvent:
            def clk() -> int:
                yield 10
                self.clk = ~self.clk
                yield 10
                self.clk = ~self.clk

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
            for i in range(3000):
                now = yield from clk()

            print(f"Done at {now}")

    test.simulation(mc6845_tb)
'''
if __name__ == "__main__":
    test_verilog()
    #test_sim()

