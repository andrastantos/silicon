from .module import Module, GenericModule
from .rv_interface import ReadyValid
from .port import Input, Output, Wire, AutoInput
from .primitives import Select, Reg, SelectOne
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
        if not isinstance(depth, int):
            raise SyntaxErrorException("Fifo depth must be an integer")
        self.depth = depth

    def body(self):
        full = Wire(logic)
        empty = Wire(logic)
        next_full = Wire(logic)
        next_empty = Wire(logic)

        self.output_port.set_net_type(self.input_port.get_net_type())

        input_data = self.input_port.get_data_members()

        self.input_port.ready <<= ~full
        self.output_port.valid <<= ~empty

        addr_type = Number(min_val=0, max_val=self.depth-1)
        data_type = input_data.get_net_type()

        output_data = Wire(data_type)

        push_addr = Wire(addr_type)
        next_push_addr = Wire(addr_type)
        pop_addr = Wire(addr_type)
        next_pop_addr = Wire(addr_type)

        push = ~full & self.input_port.valid
        pop = ~empty & self.output_port.ready

        looped = Wire(logic)
        next_looped = Wire(logic)

        push_will_wrap = push_addr == self.depth-1
        pop_will_wrap = pop_addr == self.depth-1
        next_push_addr <<= Select(push, push_addr, addr_type(Select(push_will_wrap, push_addr+1, 0)))
        next_pop_addr <<= Select(pop, pop_addr, addr_type(Select(pop_will_wrap, pop_addr+1, 0)))

        next_looped <<= SelectOne(
            (push != 1) & (pop != 1), looped,
            (push == 1) & (pop != 1), Select(push_will_wrap, looped, 1),
            (push != 1) & (pop == 1), Select(pop_will_wrap, looped, 0),
            (push == 1) & (pop == 1), SelectOne(
                (push_will_wrap != 1) & (pop_will_wrap != 1), looped,
                (push_will_wrap == 1) & (pop_will_wrap != 1), 1,
                (push_will_wrap != 1) & (pop_will_wrap == 1), 0,
                (push_will_wrap == 1) & (pop_will_wrap == 1), looped
            ),
        )

        next_empty_or_full = next_push_addr == next_pop_addr
        next_empty <<= Select(next_empty_or_full, 0, ~next_looped)
        next_full <<= Select(next_empty_or_full, 0, next_looped)

        push_addr <<= Reg(next_push_addr)
        pop_addr <<= Reg(next_pop_addr)
        empty <<= Reg(next_empty)
        full <<= Reg(next_full)
        looped <<= Reg(next_looped)

        # Buffer memory
        mem_config = MemoryConfig((
            MemoryPortConfig(addr_type, data_type, registered_input=True, registered_output=False),
            MemoryPortConfig(addr_type, data_type, registered_input=True, registered_output=False)
        ))
        buffer = Memory(mem_config)

        buffer.port1_data_in <<= input_data
        buffer.port1_addr <<= push_addr
        buffer.port1_write_en <<= push
        output_data <<= buffer.port2_data_out
        buffer.port2_addr <<= next_pop_addr
        self.output_port.set_data_members(output_data)


