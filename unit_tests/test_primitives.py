#!/usr/bin/python3
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / ".."))

from typing import *

from silicon import *
import silicon
from test_utils import *

import inspect

def test_select():
    class top(Module):
        sout1 = Output(Signed(length=5))
        uin1 = Input(Unsigned(length=2))
        uin2 = Input(Unsigned(length=4))
        sin1 = Input(Signed(length=4))
        sin2 = Input(Signed(length=4))
        sel_in = Input(Unsigned(2))

        def body(self):
            #self.sout1 <<= Select(self.sel_in, self.uin1, self.uin2, self.sin1, default=self.sin2)
            self.sout1 <<= Select(self.sel_in, self.uin1, self.uin2, self.sin1, self.sin2)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_select_with_none():
    class top(Module):
        sout1 = Output(Signed(length=5))
        uin1 = Input(Unsigned(length=2))
        uin2 = Input(Unsigned(length=4))
        sin1 = Input(Signed(length=4))
        sin2 = Input(Signed(length=4))
        sel_in = Input(Unsigned(2))

        def body(self):
            #self.sout1 <<= Select(self.sel_in, self.uin1, self.uin2, self.sin1, default=self.sin2)
            self.sout1 <<= Select(self.sel_in, self.uin1, self.uin2, self.sin1, self.sin2, None)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_mux():
    class top(Module):
        in1 = Input(Unsigned(length=4))
        in2 = Input(Unsigned(length=4))
        sel = Input(logic)
        out1 = Output(Unsigned(length=4))

        def body(self):
            self.out1 <<= Select(self.sel, self.in1, self.in2)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_enum_mux():
    class branch_ops(Enum):
        unknown   = 0

        cb_eq     = 1
        cb_ne     = 2
        cb_unk    = 14

    class top(Module):
        in1 = Input(EnumNet(branch_ops))
        in2 = Input(EnumNet(branch_ops))
        sel1 = Input(logic)
        sel2 = Input(logic)
        sel3 = Input(logic)
        sel_none = Input(logic)
        out1 = Output(EnumNet(branch_ops))

        def body(self):
            self.out1 <<= SelectOne(
                self.sel_none, None,
                self.sel1, self.in1,
                self.sel2, self.in2,
                self.sel3, branch_ops.cb_eq,
                default_port=branch_ops.cb_unk
            )

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


def test_select_one_first():
    class top(Module):
        sout1 = Output(Signed(length=11))
        sout2 = Output(Signed(length=11))
        sout3 = Output(Signed(length=11))
        sout4 = Output(Signed(length=11))
        sout5 = Output(Signed(length=11))
        val_in1 = Input(Unsigned(length=2))
        val_in2 = Input(Unsigned(length=4))
        val_in3 = Input(Signed(length=4))
        val_in4 = Input(Signed(length=4))
        default_port = Input(Unsigned(length=8))
        sel_in1 = Input(Unsigned(length=2))
        sel_in2 = Input(Unsigned(length=1))
        sel_in3 = Input(Signed(length=2))
        sel_in4 = Input(Signed(length=1))

        def body(self):
            self.sout1 <<= SelectOne(self.sel_in1, self.val_in1, self.sel_in2, self.val_in2, self.sel_in3, self.val_in3, self.sel_in4, self.val_in4, default_port=self.default_port)
            self.sout2 <<= SelectFirst(self.sel_in1, self.val_in1, self.sel_in2, self.val_in2, self.sel_in3, self.val_in3, self.sel_in4, self.val_in4, default_port=self.default_port)
            self.sout3 <<= SelectFirst(self.sel_in1, self.val_in1, self.sel_in2, self.val_in2, self.sel_in3, self.val_in3, selector_3=self.sel_in4, value_3=self.val_in4, default_port=self.default_port)
            self.sout4 <<= SelectFirst(self.sel_in1, self.val_in1, self.sel_in2, self.val_in2, self.sel_in3, self.val_in3, value_3=self.val_in4, selector_3=self.sel_in4, default_port=self.default_port)
            self.sout5 <<= SelectFirst(
                selector_2=self.sel_in3, value_2=self.val_in3,
                selector_1=self.sel_in2, value_1=self.val_in2,
                selector_3=self.sel_in4, value_3=self.val_in4,
                selector_0=self.sel_in1, value_0=self.val_in1,
                default_port=self.default_port
            )

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_select_first_sim():
    class top(Module):
        selectors = Input(Unsigned(4))
        in1 = Input(Unsigned(8))
        in2 = Input(Unsigned(8))
        in3 = Input(Unsigned(8))
        in4 = Input(Unsigned(8))
        o = Output(Unsigned(8))

        def body(self):
            self.o <<= SelectFirst(
                self.selectors[0], self.in1,
                self.selectors[1], self.in2,
                self.selectors[2], self.in3,
                self.selectors[3], self.in4,
            )

        def simulate(self, simulator):
            self.in1 <<= 1
            self.in2 <<= 2
            self.in3 <<= 3
            self.in4 <<= 4
            self.selectors <<= 0b0001
            yield 0 # FIXME: Not sure exactly why we need a double-delta wait here.
            yield 0
            simulator.sim_assert(self.o == self.in1)
            self.selectors <<= 0b0010
            yield 0
            simulator.sim_assert(self.o == self.in2)
            self.selectors <<= 0b0100
            yield 0
            simulator.sim_assert(self.o == self.in3)
            self.selectors <<= 0b1000
            yield 0
            simulator.sim_assert(self.o == self.in4)

    test.simulation(top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)


class Sel(Interface):
    sel1 = logic
    sel2 = logic
    sel3 = logic
    sel4 = logic

def test_select_first_sim2():
    class top(Module):
        selectors = Input(Sel)
        in1 = Input(Unsigned(8))
        in2 = Input(Unsigned(8))
        in3 = Input(Unsigned(8))
        in4 = Input(Unsigned(8))
        o = Output(Unsigned(8))

        def body(self):
            self.o <<= SelectFirst(
                self.selectors.sel1, self.in1,
                self.selectors.sel2, self.in2,
                self.selectors.sel3, self.in3,
                self.selectors.sel4, self.in4,
            )

        def simulate(self, simulator):
            self.in1 <<= 1
            self.in2 <<= 2
            self.in3 <<= 3
            self.in4 <<= 4
            self.selectors.sel1 <<= 1
            self.selectors.sel2 <<= 0
            self.selectors.sel3 <<= 0
            self.selectors.sel4 <<= 0
            yield 0 # FIXME: Not sure exactly why we need a double-delta wait here.
            yield 0
            simulator.sim_assert(self.o == self.in1)
            self.selectors.sel1 <<= 0
            self.selectors.sel2 <<= 1
            self.selectors.sel3 <<= 0
            self.selectors.sel4 <<= 0
            yield 0
            simulator.sim_assert(self.o == self.in2)
            self.selectors.sel1 <<= 0
            self.selectors.sel2 <<= 0
            self.selectors.sel3 <<= 1
            self.selectors.sel4 <<= 0
            yield 0
            simulator.sim_assert(self.o == self.in3)
            self.selectors.sel1 <<= 0
            self.selectors.sel2 <<= 0
            self.selectors.sel3 <<= 0
            self.selectors.sel4 <<= 1
            yield 0
            simulator.sim_assert(self.o == self.in4)

    test.simulation(top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)

def test_reg():
    class top(Module):
        sout1 = Output(Signed(length=5))
        uout1 = Output(Signed(length=5))
        uout2 = Output(Signed(length=5))
        uout3 = Output(Signed(length=5))
        uout4 = Output(Signed(length=5))
        uin1 = Input(Unsigned(length=2))
        uin2 = Input(Unsigned(length=4))
        clk1 = Input(logic)
        clk2 = Input(logic)

        def body(self):
            clk = self.clk1
            self.sout1 <<= Reg(self.uin1, clock_port=self.clk1)
            registered = Reg(self.uin2)
            self.uout1 <<= registered
            reset_reg = Reg(self.uin1, reset_value_port=3, reset_port=self.uin2[1])
            reset = self.uin2[0]
            reset_reg2 = Reg(self.uin1, reset_value_port=2)
            with self.clk2 as clk:
                self.uout2 <<= Reg(self.uin2)
            #self.uout3 = Reg(self.uin1)
            clk = self.clk1
            self.uout3 <<= Reg(self.uin1)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_reg_with_adaptor():
    class top(Module):
        uout1 = Output(Signed(length=5))
        uin2 = Input(Unsigned(length=4))
        clk = ClkPort()

        def body(self):
            registered = Reg(self.uin2)
            self.uout1 <<= registered

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_reg3():
    class top(Module):
        sout1 = Output(Signed(length=5))
        uout1 = Output(Signed(length=5))
        uout2 = Output(Signed(length=5))
        uout3 = Output(Signed(length=5))
        uout4 = Output(Signed(length=5))
        uin1 = Input(Unsigned(length=2))
        uin2 = Input(Unsigned(length=4))
        clk = ClkPort()
        clk2 = ClkPort(auto_port_names = ("clk2", "clk2_port", "clock2", "clock2_port"))

        def body(self):
            clk = self.clk
            self.sout1 <<= Reg(self.uin1, clock_port=self.clk)
            registered = Reg(self.uin2)
            self.uout1 <<= registered
            reset_reg = Reg(self.uin1, reset_value_port=3, reset_port=self.uin2[1])
            reset = Wire()
            reset <<= self.uin2[0]
            reset_reg2 = Reg(self.uin1, reset_value_port=2)
            with self.clk2 as clk:
                self.uout2 <<= Reg(self.uin2)
            self.uout3 <<= Reg(self.uin1)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_reg3b():
    class top(Module):
        uout3 = Output(Signed(length=5))
        uin1 = Input(Unsigned(length=2))
        clk = ClkPort()

        def body(self):
            # The code below will - unintuitively create two slice instances and some ugliness in the RTL.
            # The reason for it is that the local variable, `reset`, is a reference to a UniSlice instance.
            # So the binding of it to the reset port of `Reg` ends up calling convert_to_junction. Then,
            # when the tracer gets its turn, it'll do it again for `reset`. This means however that at this
            # point `reset` is not actually the input to the reset port of Reg. In fact, it doesn't even have
            # anything to do with the fact that it's an autoport. It happens with even and `&` gate.
            # It's just more visible here because of the ugly intermediate wire name that gets generated.
            # If the commented code is used, where we force `reset` to be a Junction, instead of a UniSlice,
            # we 'fix' the problem, however that's not really pythonic...
            """
            reset = Wire()
            reset <<= self.uin1[0]
            """
            reset = self.uin1[0]
            self.uout3 <<= Reg(self.uin1)

    set_verbosity_level(VerbosityLevels.instantiation)
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_reg4():
    class top(Module):
        sout1 = Output(Signed(length=5))
        uin1 = Input(Unsigned(length=2))
        clk1 = Input(logic)

        def body(self):
            self.sout1 <<= Reg(self.uin1, clock_port=(self.clk1 & self.uin1[0]))

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_reg5():
    class top(Module):
        sout1 = Output(Unsigned(length=2))
        uin1 = Input(Unsigned(length=2))
        clk = Input(logic)

        def body(self):
            self.sout1 <<= Reg(self.uin1)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_partial_assign():
    class top(Module):
        out1 = Output(Unsigned(length=5))
        in1 = Input(Unsigned(length=2))

        def body(self):
            self.out1[2:0] <<= self.in1
            self.out1[4:3] <<= self.in1

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

@skip_iverilog
def test_unassigned_net_repro():
    class top(Module):
        clk = ClkPort()
        rst = RstPort()

        fetch = Input(Unsigned(32))
        push_data = Output(Unsigned(32))

        def body(self):
            btm_inst_reg = Wire(Unsigned(32))
            btm_inst_reg[31:16] <<= Reg(self.fetch[31:16])
            btm_inst_reg[15:0] <<= Reg(self.fetch[15:0])
            #btm_inst_reg <<= concat(
            #    Reg(self.fetch[31:16]),
            #    Reg(self.fetch[15:0])
            #)
            self.push_data[31:16] <<= Reg(self.fetch[31:16])
            self.push_data[15:0] <<= Reg(self.fetch[15:0])
            s1 = Wire(logic)
            s1 <<= 1
            sfd = Wire(Unsigned(32))
            sfd <<= self.fetch
            inst_btm_top = Select(
                s1,
                btm_inst_reg,
                sfd
            )
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


def test_const_cast():
    class top(Module):
        #fetch = Input(Unsigned(32))
        push_data = Output(Unsigned(32))

        def body(self):
            self.push_data <<= cast(3, Unsigned(32))
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_large_select():
    class top(Module):
        i = Input(Unsigned(32))
        s = Input(Unsigned(5))
        o = Output(logic)

        def body(self):
            self.o <<= Select(self.s, *self.i)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_large_select_one():
    class top(Module):
        i = Input(Unsigned(5))
        s = Input(Unsigned(5))
        o = Output(logic)

        def body(self):
            list = []
            for s, i in zip(self.s, self.i):
                list += (s, i)
            self.o <<= SelectOne(*list)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_default_select():
    class top(Module):
        i = Input(Unsigned(3))
        s = Input(Unsigned(2))
        d = Input(logic)
        o = Output(logic)

        def body(self):
            self.o <<= Select(self.s, *self.i, default_port=self.d)

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)


def test_latch(mode: str = "sim"):
    class top(Module):
        in1 = Input(Unsigned(8))
        out1 = Output(Unsigned(8))
        clk = ClkPort()
        rst = RstPort()
        enable = Input(logic)

        def body(self):
            dut = LatchReg()
            self.out1 <<= dut(self.in1)
            dut.enable <<= self.enable

    class sim_top(Module):
        clk = ClkPort()
        rst = RstPort()

        def body(self):
            self.data = Wire(Unsigned(8))
            self.check = Wire(Unsigned(8))
            self.enable = Wire(logic)
            dut = top()
            dut.rst <<= self.rst
            dut.clk <<= self.clk
            self.check <<= dut(self.data)
            dut.enable <<= self.enable

        def simulate(self) -> TSimEvent:
            def clk():
                yield 10
                self.clk <<= ~self.clk & self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0

            print("Simulation started")

            self.rst <<= 1
            self.clk <<= 1
            self.enable <<= 0
            yield 10
            for i in range(5):
                yield from clk()
            self.rst <<= 0

            yield from clk()
            self.data <<= 1
            self.enable <<= 1
            yield 0
            assert self.check == 1
            yield from clk()
            assert self.check == 1
            self.enable <<= 0
            self.data <<= 2
            yield 0
            assert self.check == 1
            yield from clk()
            assert self.check == 1
            self.enable <<= 1
            yield 0
            assert self.check == 2
            yield from clk()
            assert self.check == 2
            now = yield 10
            print(f"Done at {now}")

    if mode == "rtl":
        test.rtl_generation(top, inspect.currentframe().f_code.co_name)
    else:
        test.simulation(sim_top, inspect.currentframe().f_code.co_name, add_unnamed_scopes=True)

def test_latch_sim(): test_latch("sim")
def test_latch_rtl(): test_latch("rtl")

if __name__ == "__main__":
    #test_select()
    #test_select_one_first()
    #test_reg()
    #test_reg3()
    #test_reg3b()
    #test_reg4()
    #test_reg5()
    #test_mux()
    #test_select_with_none()
    #test_reg4()
    #test_reg_with_adaptor()
    #test_partial_assign()
    #test_unassigned_net_repro()
    #test_const_cast()
    #test_large_select()
    #test_default_select()
    #test_large_select_one()
    #test_select_first_sim()
    #test_select_first_sim2()
    #test_latch("sim")
    test_enum_mux()