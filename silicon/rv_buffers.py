from .module import Module, GenericModule
from .rv_interface import ReadyValid
from .port import Input, Output, Wire, AutoInput
from .primitives import Select, Reg
from .exceptions import SyntaxErrorException
from .utils import is_input_port, is_output_port
from .number import Number, logic
from .utils import get_composite_member_name
from collections import OrderedDict
from .memory import MemoryPortConfig, MemoryConfig, Memory

class ForwardBuf(Module):
    input_port = Input()
    output_port = Output()
    clock_port = AutoInput(auto_port_names=("clk", "clk_port", "clock", "clock_port"), optional=False)
    reset_port = AutoInput(auto_port_names=("rst", "rst_port", "reset", "reset_port"), optional=False)

    def body(self):
        in_ready = self.input_port.ready
        in_valid = self.input_port.valid

        self.output_port.set_net_type(self.input_port.get_net_type())

        data = self.input_port.get_data_members()

        out_ready = Wire(logic)
        buf_valid = Wire(logic)
        buf_data = Wire(data.get_net_type()) # At this point we have to create a typed wire. TODO: can we make it so that we don't?

        buf_data <<= Reg(Select(in_valid & in_ready, buf_data, data))
        buf_valid <<= Reg(Select(in_valid & in_ready, Select(out_ready & buf_valid, buf_valid, 0), 1))

        self.output_port.set_data_members(buf_data)

        self.output_port.valid <<= buf_valid
        out_ready <<= self.output_port.ready
        in_ready <<= ~buf_valid | out_ready

        # Clean up the namespace
        del(out_ready)
        del(in_valid)
        del(data)


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
        data = self.input_port.get_data_members()

        self.output_port.set_net_type(self.input_port.get_net_type())

        buf_data = Wire(data.get_net_type()) # At this point we have to create a typed wire. TODO: can we make it so that we don't?
        buf_data <<= Reg(Select(buf_load, buf_data, data))

        out_ready = self.output_port.ready
        in_ready <<= Reg(out_ready)

        buf_load <<= in_valid & in_ready & ~out_ready

        buf_valid <<= Reg(Select(out_ready, Select(buf_load, buf_valid, 1), 0))

        self.output_port.valid = Select(out_ready & ~buf_valid, buf_valid, in_valid & in_ready)

        out_data = Wire(data.get_net_type())
        out_data <<= Select(out_ready & ~buf_valid, buf_data, data)
        self.output_port.set_data_members(out_data)

        # Clean up the namespace
        del(out_data)
        del(data)
        del(out_ready)
        del(in_valid)


class Fifo(GenericModule):
    input_port = Input()
    output_port = Output()
    clock_port = AutoInput(auto_port_names=("clk", "clk_port", "clock", "clock_port"), optional=False)
    reset_port = AutoInput(auto_port_names=("rst", "rst_port", "reset", "reset_port"), optional=False)

    def construct(self, depth:int):
        self.depth = depth

    def body(self):
        full = Wire(logic)
        empty = Wire(logic)

        self.output_port.set_net_type(self.input_port.get_net_type())

        input_data = self.input_port.get_data_members()

        self.input_port.ready <<= ~full
        self.output_port.valid <<= ~empty

        addr_type = Number(min=0, max=self.depth-1)

        data_type = input_data.get_net_type()

        output_data = Wire(data_type)

        push_addr = Wire(addr_type)
        pop_addr = Wire(addr_type)

        push = ~full & self.input_port.valid
        pop = ~empty & self.output_port.ready

        looped = Wire(logic)

        push_will_wrap = push_addr == self.depth-1
        pop_will_wrap = pop_addr == self.depth-1
        push_addr <<= Reg(Select(push, push_addr, Select(push_will_wrap, push_addr+1, 0)))
        pop_addr <<= Reg(Select(pop, pop_addr, Select(pop_will_wrap, pop_addr+1, 0)))

        next_looped = Select(push, Select(pop, looped, Select(pop_will_wrap, looped, 0)), Select(push_will_wrap, looped, 1))
        looped <<= Reg(next_looped)

        empty_or_full = push_addr == pop_addr
        empty <<= Reg(Select(empty_or_full, 0, ~next_looped))
        full <<= Reg(Select(empty_or_full, 0, next_looped))

        # Buffer memory
        mem_config = MemoryConfig((MemoryPortConfig(addr_type, data_type, registered_input=True, registered_output=False),MemoryPortConfig(addr_type, data_type, registered_input=True, registered_output=False)))
        buffer = Memory(mem_config)

        buffer.port1_data_in <<= input_data
        buffer.port1_addr <<= push_addr
        buffer.port1_write_en <<= push
        output_data <<= buffer.port2_data_out
        buffer.port2_addr <<= pop_addr


