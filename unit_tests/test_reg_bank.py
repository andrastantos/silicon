#!pytest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".."))
from silicon import *
from silicon.utils import VerbosityLevels
from test_utils import *
import inspect
import pytest

def test_single_reg(mode = "rtl"):
    class Top(Module):
        clk = ClkPort()
        rst = RstPort()

        paddr = Input(Unsigned(10))
        psel = Input(logic)
        penable = Input(logic)
        prdata = Output(Unsigned(32))
        pwdata = Input(Unsigned(32))
        pwrite = Input(logic)
        pready = Output(logic)

        def body(self):
            bus = Wire(ApbIf(Unsigned(32)))
            bus.paddr <<= self.paddr
            bus.psel <<= self.psel
            bus.penable <<= self.penable
            bus.pwdata <<= self.pwdata
            bus.pwrite <<= self.pwrite
            self.pready <<= bus.pready
            self.prdata <<= bus.prdata

            reg0 = Wire(Unsigned(32))
            reg1a = Wire(Unsigned(16))
            reg1b = Wire(Unsigned(16))
            regs = {
                0: RegMapEntry("booooo", reg0 ),
                #1: RegMapEntry("b2", (reg1a, reg1b))
            }

            create_apb_reg_map(regs, bus, 0x400)

    if mode == "rtl":
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        #test.simulation(top_tb, "test_enum1")
        pass

def test_2_regs(mode = "rtl"):
    class Top(Module):
        clk = ClkPort()
        rst = RstPort()

        paddr = Input(Unsigned(10))
        psel = Input(logic)
        penable = Input(logic)
        prdata = Output(Unsigned(32))
        pwdata = Input(Unsigned(32))
        pwrite = Input(logic)
        pready = Output(logic)

        def body(self):
            bus = Wire(ApbIf(Unsigned(32)))
            bus.paddr <<= self.paddr
            bus.psel <<= self.psel
            bus.penable <<= self.penable
            bus.pwdata <<= self.pwdata
            bus.pwrite <<= self.pwrite
            self.pready <<= bus.pready
            self.prdata <<= bus.prdata

            reg0 = Wire(Unsigned(32))
            reg1a = Wire(Unsigned(16))
            reg1b = Wire(Unsigned(16))
            regs = {
                0: RegMapEntry("booooo", reg0 ),
                1: RegMapEntry("b2", (reg1a, reg1b))
            }

            create_apb_reg_map(regs, bus, 0x400)

    if mode == "rtl":
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        #test.simulation(top_tb, "test_enum1")
        pass


def test_field_regs(mode = "rtl"):
    class Top(Module):
        clk = ClkPort()
        rst = RstPort()

        paddr = Input(Unsigned(10))
        psel = Input(logic)
        penable = Input(logic)
        prdata = Output(Unsigned(32))
        pwdata = Input(Unsigned(32))
        pwrite = Input(logic)
        pready = Output(logic)

        def body(self):
            bus = Wire(ApbIf(Unsigned(32)))
            bus.paddr <<= self.paddr
            bus.psel <<= self.psel
            bus.penable <<= self.penable
            bus.pwdata <<= self.pwdata
            bus.pwrite <<= self.pwrite
            self.pready <<= bus.pready
            self.prdata <<= bus.prdata

            reg0 = Wire(Unsigned(32))
            reg1a = Wire(Unsigned(16))
            reg1b = Wire(Unsigned(16))
            reg2a = Wire(Unsigned(8))
            reg2b = Wire(Unsigned(8))
            regs = {
                0: RegMapEntry("booooo", reg0 ),
                1: RegMapEntry("b2", (reg1a, reg1b)),
                10: RegMapEntry("b3", (RegField(reg2a, 24), RegField(reg2b, 8)))
            }

            create_apb_reg_map(regs, bus, 0x400)

    if mode == "rtl":
        test.rtl_generation(Top, inspect.currentframe().f_code.co_name)
    else:
        #test.simulation(top_tb, "test_enum1")
        pass

if __name__ == "__main__":
    test_field_regs()
