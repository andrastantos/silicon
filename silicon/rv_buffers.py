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
        in_ready = None
        in_valid = None
        data_signals = OrderedDict()
        for names, input_member in self.input_port.get_all_member_junctions_with_names(add_self=False).items():
            if names == ("valid",):
                in_valid = input_member
            elif names == ("ready", ):
                in_ready = input_member
            else:
                if not is_input_port(input_member):
                    raise SyntaxErrorException(f"data member {get_composite_member_name(names)} signal in input port should be not reversed while evaluating {self}")
                data_signals[names] = input_member
        if in_ready is None:
            raise SyntaxErrorException(f"Input port doesn't have a 'ready' member while evaluating {self}")
        if in_valid is None:
            raise SyntaxErrorException(f"Input port doesn't have a 'valid' member while evaluating {self}")
        if not is_output_port(in_ready):
            raise SyntaxErrorException(f"ready signal in input port should be reversed while evaluating {self}")
        if not is_input_port(in_valid):
            raise SyntaxErrorException(f"valid signal in input port should be not reversed while evaluating {self}")

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

        for names, output_member in self.output_port.get_all_member_junctions_with_names(add_self=False).items():
            if names not in (("valid",), ("ready", )):
                output_member <<= buf_data[names]

        self.output_port.valid <<= buf_valid
        out_ready <<= self.output_port.ready
        in_ready <<= ~buf_valid | out_ready

        # Clean up the namespace
        del(data_signals)
        del(buf_data)
        del(buf_member)
        del(output_member)
        del(input_member)
        del(member)
        del(out_ready)
        del(in_valid)