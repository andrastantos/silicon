from .module import Module, GenericModule
from .rv_interface import ReadyValid
from .port import Input, Output, Wire
from .auto_input import ClkPort, RstPort
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
    clock_port = ClkPort()
    reset_port = RstPort()

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
    clock_port = ClkPort()
    reset_port = RstPort()

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

        self.output_port.valid <<= Select(out_ready & ~buf_valid, buf_valid, in_valid & in_ready)

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
    clock_port = ClkPort()
    reset_port = RstPort()

    def construct(self, depth:int):
        try:
            self.depth = int(depth)
        except TypeError:
            raise SyntaxErrorException("Fifo depth must be an integer")

    def body(self):
        if self.depth == 0:
            self.output_port <<= self.input_port
        elif self.depth == 1:
            self.output_port <<= ForwardBuf(self.input_port)
        else:
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
            empty <<= Reg(next_empty, reset_value_port = 1)
            full <<= Reg(next_full)
            looped <<= Reg(next_looped)

            # Buffer memory
            mem_config = MemoryConfig((
                MemoryPortConfig(addr_type, data_type, registered_input=True, registered_output=False),
                MemoryPortConfig(addr_type, data_type, registered_input=True, registered_output=False)
            ))
            buffer_mem = Memory(mem_config)

            buffer_mem.port1_data_in <<= input_data
            buffer_mem.port1_addr <<= push_addr
            buffer_mem.port1_write_en <<= push
            # Since RAM has read-old-value semantics for the case where read and write address matches,
            # we need a bypass pass to get rid of the extra cycle of latency.
            # TODO: Can we do better? We could probably change the logic to take the extra cycle into account.
            #       This way output_data is not registered.
            output_data <<= Select(
                push_addr == next_pop_addr,
                buffer_mem.port2_data_out,
                Reg(input_data)
            )
            buffer_mem.port2_addr <<= next_pop_addr
            self.output_port.set_data_members(output_data)


"""
TODO:

- DelayLine should have an implementation variant that uses a FiFo buffer - sort of line-buffer-style behavior
- These two delay-line implementations should be checked against one another for no difference in behavior
"""
class DelayLine(GenericModule):
    input_port = Input()
    output_port = Output()
    clock_port = ClkPort()
    reset_port = RstPort()

    def construct(self, depth:int):
        try:
            self.depth = int(depth)
        except TypeError:
            raise SyntaxErrorException("DelayLine depth must be an integer")

    def body(self):
        intermediate = self.input_port
        for i in range(self.depth):
            intermediate = ForwardBuf(intermediate)
        self.output_port <<= intermediate


class Pacer(GenericModule):
    input_port = Input()
    output_port = Output()
    clock_port = ClkPort()
    reset_port = RstPort()

    def construct(self, wait_states:int):
        try:
            self.wait_states = int(wait_states)
        except TypeError:
            raise SyntaxErrorException("Number of wait states must be an integer")

    def body(self):
        wait_cnt_type = Number(min_val=0, max_val=self.wait_states-1)

        wait_cnt = Wire(wait_cnt_type)
        next_wait_cnt = Wire(wait_cnt_type)


        self.output_port.set_net_type(self.input_port.get_net_type())

        input_data = self.input_port.get_data_members()

        wait_done = wait_cnt == self.wait_states-1

        self.input_port.ready <<= wait_done & self.output_port.ready
        self.output_port.valid <<= wait_done & self.input_port.valid

        transfer = self.input_port.valid & self.output_port.ready & wait_done

        next_wait_cnt <<= Select(transfer, wait_cnt_type(Select(wait_done, wait_cnt+1, self.wait_states-1)), 0)
        wait_cnt <<= Reg(next_wait_cnt)

        self.output_port.set_data_members(input_data)
