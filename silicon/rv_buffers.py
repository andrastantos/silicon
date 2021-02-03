from .module import Module
from .rv_interface import ReadyValid
from .port import Input, Output, Wire, AutoInput
from .primitives import Select, Reg
from .exceptions import SyntaxErrorException
from .utils import is_input_port, is_output_port
from .number import Number, logic
from .utils import get_composite_member_name
from collections import OrderedDict

class ForwardBuf(Module):
    input_port = Input()
    output_port = Output()
    clock_port = AutoInput(auto_port_names=("clk", "clk_port", "clock", "clock_port"), optional=False)
    reset_port = AutoInput(auto_port_names=("rst", "rst_port", "reset", "reset_port"), optional=False)

    def body(self):
        in_ready = self.input_port.ready
        in_valid = self.input_port.valid
        data_signals = self.input_port.get_data_members()

        self.output_port.set_net_type(self.input_port.get_net_type())

        out_ready = Wire(logic)
        buf_valid = Wire(logic)
        # Create locals for the data buffers in a round-about way, so that they show up in generated RTL decently.
        # We also generate the registers and their input muxes as we're there anyways.
        buf_data = OrderedDict()
        for names, member in data_signals.items():
            buf_member = Wire(member.get_net_type())
            buf_data[names] = buf_member
            exec_str = f"buf_data_{get_composite_member_name(names, '_')} = buf_member"
            exec(exec_str)
            buf_member <<= Reg(Select(in_valid & in_ready, buf_member, member))

        buf_valid <<= Reg(Select(in_valid & in_ready, Select(out_ready & buf_valid, buf_valid, 0), 1))

        for names, output_member in self.output_port.get_data_members().items():
            output_member <<= buf_data[names]

        self.output_port.valid <<= buf_valid
        out_ready <<= self.output_port.ready
        in_ready <<= ~buf_valid | out_ready

        # Clean up the namespace
        del(data_signals)
        del(buf_data)
        del(buf_member)
        del(output_member)
        del(member)
        del(out_ready)
        del(in_valid)


class ReverseBuf(Module):
    input_port = Input()
    output_port = Output()
    clock_port = AutoInput(auto_port_names=("clk", "clk_port", "clock", "clock_port"), optional=False)
    reset_port = AutoInput(auto_port_names=("rst", "rst_port", "reset", "reset_port"), optional=False)

    def body(self):
        buf_valid = Wire(logic)
        buf_load = Wire(logic)

        in_ready = self.input_port.ready
        in_valid = self.input_port.valid
        data_signals = self.input_port.get_data_members()

        self.output_port.set_net_type(self.input_port.get_net_type())

        buf_data = OrderedDict()
        for names, member in data_signals.items():
            buf_member = Wire(member.get_net_type())
            buf_data[names] = buf_member
            exec_str = f"buf_data_{get_composite_member_name(names, '_')} = buf_member"
            exec(exec_str)
            buf_member <<= Reg(Select(buf_load, buf_member, member))

        out_ready = self.output_port.ready
        in_ready <<= Reg(out_ready)

        buf_load <<= in_valid & in_ready & ~out_ready

        buf_valid <<= Reg(Select(out_ready, Select(buf_load, buf_valid, 1), 0))

        self.output_port.valid = Select(out_ready & ~buf_valid, buf_valid, in_valid & in_ready)

        for names, output_member in self.output_port.get_data_members().items():
            output_member <<= Select(out_ready & ~buf_valid, buf_data[names], data_signals[names])

        # Clean up the namespace
        del(data_signals)
        del(buf_data)
        del(buf_member)
        del(output_member)
        del(member)
        del(out_ready)
        del(in_valid)

