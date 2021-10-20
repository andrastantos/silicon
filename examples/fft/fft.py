#!/usr/bin/python3
from typing import *
from silicon import *

# We will use 16-bit integers to represent the range -2...2
DataType = Number(length=16, precision=14, signed=True)
class ComplexType(Struct):
    real = DataType
    img  = DataType

    def __eq__(self, other):
        return self.real == other.real and self.img == other.img
    def __str__(self):
        return f"({self.real}+{self.img}j)"
    def __repr__(self):
        return f"({self.real}+{self.img}j)"

class Data(ReadyValid):
    data = ComplexType()

class DataPair(ReadyValid):
    data1 = ComplexType()
    data2 = ComplexType()

class ComplexStream(ReadyValid):
    data = ComplexType()
    last = logic
class ComplexMult(Module):
    input1_port = ComplexType()
    input2_port = ComplexType()
    output_port = ComplexType()

    def body(self):
        self.output_port.real <<= self.input1_port.real * self.input2_port.real - self.input1_port.img  * self.input2_port.img
        self.output_port.img  <<= self.input1_port.img  * self.input2_port.real + self.input1_port.real * self.input2_port.img

class ComplexAdd(Module):
    input1_port = ComplexType()
    input2_port = ComplexType()
    output_port = ComplexType()

    def body(self):
        self.output_port.real <<= self.input1_port.real + self.input2_port.real
        self.output_port.img  <<= self.input1_port.img  + self.input2_port.img

class ComplexSub(Module):
    input1_port = ComplexType()
    input2_port = ComplexType()
    output_port = ComplexType()

    def body(self):
        self.output_port.real <<= self.input1_port.real - self.input2_port.real
        self.output_port.img  <<= self.input1_port.img  - self.input2_port.img

'''
class RegEn(Module):
    output_port = Output()
    input_port = Input()
    clock_port = AutoInput(auto_port_names=("clk", "clk_port", "clock", "clock_port"), optional=False)
    reset_port = AutoInput(auto_port_names=("rst", "rst_port", "reset", "reset_port"), optional=True)
    reset_value_port = AutoInput(auto_port_names=("rst_val", "rst_val_port", "reset_value", "reset_value_port"), optional=True)
    clock_en = AutoInput(auto_port_names=("clk_en", "clock_en", "clock_enable"), optional=False)

    def body(self):
        value = Wire(self.input_port.get_net_type())
        value <<= Reg(Select(self.clock_en, value, self.input_port))
        self.output_port <<= value
'''

def inc(i: Wire) -> Wire:
    return (i+1)[i.get_net_type().length-1:0]
class Butterfly(Module):
    """
    A one-number-per-clock radix-2 butterfly imlementation

    This is a bit tricky, because normally a butterfly likes to see 
    two inputs at a time and produce two outputs.

    Of course one could feed it at half rate, but that would just mean
    poor resource utilization.

    So, instead, we do a pipeline implementation.

    There's a little state-machine here, that
    
    1. accepts the first input, but produces no output.
    2. accepts the second input, produces first output
    3. accepts first input (of second butterfly) while producing second output
    4. accepts second input (of second butterfly), producing first output of second butterfly
    ...
    n+1. accepts no input, produces last output

    Now, to this essentially means an extra pipeline stage.
    There's also a pipeline stage needed for the twiddle-ROM read, but that can be folded in.
    We do need a ping-pong buffer to allow for both inputs to be present for two cycles.
    """
    clk = Input(logic)
    rst = Input(logic)

    input_data = Input(ComplexStream())
    output_data = Output(ComplexStream())

    def construct(self, twiddle_len: int):
        self.twiddle_len = twiddle_len

    def body(self):
        # Twiddle factor ROM
        config = MemoryConfig(
            (MemoryPortConfig(
                addr_type = Unsigned(self.twiddle_len),
                data_type = ComplexType(),
                registered_input = True,
                registered_output = False
            ),),
            reset_content = "xxx.bin"
        )
        mem = Memory(config)

        # Generate twiddle coefficient address
        # NOTE: bit 0 is used to select ping-pong buffer
        self.twiddle_addr = Unsigned(self.twiddle_len+1)
        self.twiddle_addr <<= Reg(
            Select(self.input_data.valid & self.input_data.ready, 
                self.twiddle_addr, 
                Select(self.input_data.last, 
                    (self.twiddle_addr + 1)[self.twiddle_len-1:0],
                    0
                )
            )
        )
        mem.addr <<= self.twiddle_addr[self.twiddle_len-1:1]
        odd_input = self.twiddle_addr[0]

        # Twiddle memory takes a cycle to read the data, so delay input by one cycle
        delayed_input_data = ForwardBuf(self.input_data)
        # Compute the butterfly (might need some pipelining, though the multipliers should support this sort of operation)
        twiddle_factor = mem.data_out 
        twiddled_data = ComplexMult(delayed_input_data.data2, twiddle_factor)
        self.output_data.data1 <<= ComplexAdd(delayed_input_data.data1, twiddled_data)
        self.output_data.data2 <<= ComplexAdd(delayed_input_data.data2, twiddled_data)

        # Output handshake
        self.output_data.valid <<= delayed_input_data.valid
        delayed_input_data.ready <<= self.output_data.ready

'''
A 16-pint FFT data-flow is shown here:
    https://docsdrive.com/images/ansinet/itj/2012/fig1-1k12-118-125.gif

Each butterfly stage (empty dots) is followed by a memory for a full frame.
Normally, a ping-pong buffer would need to be imlemented with the following addressing:
    - Writing in normal bit-order
    - Reading at level n (n=0 -> first butterfly, n=reading out final results)
      <bits [n-1:1] bits in normal order><bit [0]><bits [N-1:n] in normal order>
      final stage: bit-reversed read-out
If however we can make the read and write address the same (and using
'read-old-data' semantics on memory), we can get rid of the double-buffering
requirement. For that, we simply need to swap read and write addressing in every
frame: write in-line - read in-line, followed by write swizzeld - read swizzled.

Notice, how the data as it passes through the memory is always either:
write in-line - read swizzeld or write swizzeled - read in-line.

Also notice how this setup allows us to use a single address generator for each
memory buffer.

Finally notice that our memory reads/writes one complex number at a time, so a single
butterfly takes two cycles.
'''
class ButterflyMem(GenericModule):
    """
    Memory stage between butterflies
    """
    clk = Input(logic)
    rst = Input(logic)

    input_data = Input(ComplexStream())
    output_data = Output(ComplexStream())
    flush_in = Input(trigger)
    flush_out = Output(trigger)

    def construct(self, addr_len: int, level: int):
        self.addr_len = addr_len
        self.level = level

    def body(self):
        self.addr_cnt = Wire(Unsigned(self.addr_len))
        self.do_swizzle = Wire(logic)
        self.content_valid = Wire(logic)
        self.delayed_content_valid = Wire(logic)
        self.flushing = Wire(logic)
        self.delayed_last = Wire(logic)

        next_flushing = Select(self.flush_in,
            Select(self.output_data.ready & self.flushing & self.addr_cnt == (2**self.addr_len-1),
                self.flushing,
                0
            ),
            1
        )
        self.flushing <<= Reg(next_flushing)

        self.do_swizzle <<= Reg(
            Select(self.input_data.ready & self.input_data.valid,
                self.do_swizzle,
                Select(self.input_data.last, self.do_swizzle, ~self.do_swizzle)
            )
        )
        self.addr_cnt <<= Reg(
            Select(self.input_data.ready & self.input_data.valid, self.addr_cnt,
                Select(self.input_data.last,
                    # This is not really needed: the way next_flushing is computed, it'll go inactive when the address would roll over anyway.
                    #Select(self.flushing & ~next_flushing,
                    #    self.addr_cnt + 1,
                    #    0
                    #)
                    inc(self.addr_cnt),
                    0
                )
            )
        )
        self.content_valid <<= Reg(
            Select(self.input_data.ready & self.input_data.valid & self.input_data.last,
                #Select(next_flushing,
                #    ~self.flushing,
                #    1,
                #),
                self.flushing,
                1
            )
        )
        self.delayed_last <<= Reg(
            Select(self.input_data.ready & self.input_data.valid,
                self.delayed_last,
                self.input_data.last
            )
        )
        # TODO: Do we have to qualify the delay here? I think not, as we're only accounting for the memory read latency...
        self.delayed_content_valid <<= Reg(self.content_valid)
        addr = Select(self.do_swizzle,
            self.addr_cnt,
            (self.addr_cnt[self.addr_len-1:self.level+1], self.addr_cnt[0], self.addr_cnt[self.level-1:0])
        )

        config = MemoryConfig(
            (MemoryPortConfig(
                addr_type = Unsigned(self.addr_len),
                data_type = ComplexType(),
                registered_input = True,
                registered_output = False
            ),
            MemoryPortConfig(
                addr_type = Unsigned(self.addr_len),
                data_type = ComplexType(),
                registered_input = True,
                registered_output = False
            ),)
        )
        # Since data gets really mixed around between butterflies, and because we don't have multiple address ports on a memory,
        # We actually have four instances, one for each possible input-output combo for the elements of a DataPair
        mem = Memory(config)
        # Port 1 writes data in whenever it's ready
        mem.port1_data_in <<= self.input_data.data
        mem.port1_addr <<= addr
        mem.port1_write_en <<= self.input_data.ready & self.input_data.valid
        # Port 2 reads data whenever it's needed
        self.output_data.data <<= mem.port2_data_out
        self.output_data.last <<= self.delayed_last
        mem.port2_addr <<= addr
        # We need input and output work in tandem. Which is to say that we can only make progress if both ports are ready/valid
        self.input_data.ready <<= self.output_data.ready & ~next_flushing
        # Here we need to do a little trick, because we have a single-frame long latency
        self.output_data.valid <<= (self.input_data.valid & self.delayed_content_valid) | next_flushing
        # Propagate flush signal to next stage
        self.flush_out <<= self.flushing & ~next_flushing

