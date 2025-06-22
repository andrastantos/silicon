from .port import Input, Output, OutputPort, Wire
from .number import Unsigned, logic
from .module import Module
from .net_type import NetType
from .exceptions import SyntaxErrorException
from .gates import and_gate
from typing import Dict, Union
from enum import Enum


class OneHotDecode(Module):
    input_port = Input()

    def construct(self):
        self.decoders: Dict[int, OutputPort] = dict()

    def decode(self, value: Union[int, Enum]) -> OutputPort:
        try:
            int_value = value.value
        except AttributeError:
            int_value = int(value)
        if int_value not in self.decoders:
            self.decoders[int_value] = self.create_named_port(f"output_for_{value}", port_type=Output, net_type=logic)
        return self.decoders[int_value]

    def body(self):
        bit_cnt = self.input_port.get_num_bits()
        decoder_type = Unsigned(bit_cnt)
        in_val = Wire(decoder_type)
        in_val_n = Wire(decoder_type)
        in_val <<= decoder_type(self.input_port)
        in_val_n <<= ~in_val
        for value, out in self.decoders.items():
            if value < decoder_type.min_val or value > decoder_type.max_val:
                raise SyntaxErrorException(f"Can't decode value: {value}. It's outside of valid range for type {decoder_type}")
            # Construct an and-gate with the right (inverted or otherwise) bits
            inputs = []
            for bit in range(bit_cnt):
                if value & (1 << bit) != 0:
                    inputs.append(in_val[bit])
                else:
                    inputs.append(in_val_n[bit])
            out <<= and_gate(*inputs)



