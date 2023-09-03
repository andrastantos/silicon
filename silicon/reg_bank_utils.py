# Contains utilities to create register banks.

from typing import Tuple, Dict, Optional, Union
from .apb_bus import ApbIf, ApbBaseIf
from .number import logic
from .net_type import NetType
from .port import Junction, JunctionBase
from .exceptions import SyntaxErrorException
from itertools import chain
from dataclasses import dataclass
from .primitives import concat, SelectOne, Reg
from .utils import convert_to_junction

class RegField(object):
    def __init__(
        self, 
        wire: Junction = None,
        start_bit: Optional[int] = None,
        length: Optional[int] = None,
        access: str = "RW", # Valid entries are: R/W
        description: Optional[str] = None,
        *,
        read_wire: Junction = None,
        write_wire: Junction = None,
    ) :
        if wire is not None and (read_wire is not None or write_wire is not None):
            raise SyntaxErrorException(f"If 'wire' is specified, 'read_wire' and 'write_wire' must be None")

        self.wire          = wire
        self.read_wire     = read_wire
        self.write_wire    = write_wire
        self.start_bit     = start_bit
        self.length        = length
        self.access        = access
        self.description   = description

    def has_wire(self):
        return self.wire is not None or self.read_wire is not None or self.write_wire is not None

    def get_read_wire(self):
        return self.wire if self.wire is not None else self.read_wire
    
    def get_write_wire(self):
        return self.wire if self.wire is not None else self.write_wire
    

class RegMapEntry(object):
    def __init__(
        self,
        name: str,
        fields: Union[JunctionBase, RegField, Tuple[RegField]], # Fields must be listed in decrementing start-bit, i.e. from left to right
        description: Optional[str] = None,
        *,
        read_pulse: Optional[Junction] = None,
        write_pulse: Optional[Junction] = None,
    ):
        self.name = name
        self.fields = fields
        self.read_pulse = read_pulse
        self.write_pulse = write_pulse
        self.description = description

    def get_fields(self):
        if isinstance(self.fields, JunctionBase):
            return (RegField(self.fields),)
        if isinstance(self.fields, RegField):
            return (self.fields, )
        ret_val = []
        for field in self.fields:
            if isinstance(field, JunctionBase):
                ret_val.append(RegField(field))
            else:
                ret_val.append(field)
        return ret_val
    
    def create_read_concatenation(self) -> Optional[Junction]:
        top_bit_idx = 0
        concat_list = []
        used = False
        fields = self.get_fields()
        for i, field in enumerate(reversed(fields)):
            idx = len(fields)-i
            start_bit = field.start_bit if field.start_bit is not None else top_bit_idx
            if start_bit < top_bit_idx:
                raise SyntaxErrorException(f"Field {idx} in register map entry {self.name} start bit is too low {field.start_bit}, minimum allowed: {top_bit_idx}")
            if start_bit > top_bit_idx:
                concat_list.append(f"{start_bit-top_bit_idx}'b0")
            top_bit_idx = start_bit
            wire = field.get_read_wire()
            if field.length is None and wire is None:
                raise SyntaxErrorException(f"Field {idx} in register map entry {self.name} must have either a wire or a length specified")
            if field.length is not None and wire is not None:
                raise SyntaxErrorException(f"Field {idx} in register map entry {self.name} can't have both a wire and length specified")
            field_length = field.length if field.length is not None else convert_to_junction(wire).get_num_bits()
            if "R" in field.access:
                concat_list.append(wire)
                used = True
            else:
                concat_list.append(f"{field_length}'b0")
            top_bit_idx += field_length
        if not used:
            return None
        return concat(*reversed(concat_list))

    def create_reg(self, pwdata, write_pulse) -> None:
        top_bit_idx = 0
        concat_list = []
        fields = self.get_fields()
        for i, field in enumerate(reversed(fields)):
            idx = len(fields)-i
            start_bit = field.start_bit if field.start_bit is not None else top_bit_idx
            wire = field.get_write_wire()
            if start_bit < top_bit_idx:
                raise SyntaxErrorException(f"Field {idx} in register map entry {self.name} start bit is too low {field.start_bit}, minimum allowed: {top_bit_idx}")
            if field.length is None and wire is None:
                raise SyntaxErrorException(f"Field {idx} in register map entry {self.name} must have either a wire or a length specified")
            if field.length is not None and wire is not None:
                raise SyntaxErrorException(f"Field {idx} in register map entry {self.name} can't have both a wire and length specified")
            top_bit_idx = start_bit
            field_length = field.length if field.length is not None else convert_to_junction(wire).get_num_bits()
            if "W" in field.access:
                if wire is None:
                    raise SyntaxErrorException(f"Field {idx} in register map entry {self.name}: writable fields must have a wire specified")
                wire <<= Reg(pwdata[top_bit_idx+field_length-1:top_bit_idx], clock_en=write_pulse)
            top_bit_idx += field_length

def create_apb_reg_map(regs: Dict[int, RegMapEntry], bus: ApbBaseIf, base: Optional[int] = None):
    max_ofs = max(regs.keys())
    ofs_bits = max_ofs.bit_length()
    if base is not None:
        if base & ((1 << ofs_bits)-1) != 0:
            raise SyntaxErrorException(f"Register map base {base} needs its bottom {ofs_bits} bits cleared")
        page = base >> ofs_bits
        paddr_page = bus.paddr[:ofs_bits]
        access_strobe = (paddr_page == page) & bus.psel & bus.penable
    else:
        access_strobe = bus.psel & bus.penable
    paddr_offs = bus.paddr[ofs_bits-1:0] if ofs_bits > 0 else None
    bus.pready <<= 1
    read_strobe = access_strobe & ~bus.pwrite & bus.pready
    write_strobe = access_strobe & bus.pwrite & bus.pready
    read_map = {}
    for offs, reg in regs.items():
        read_val = reg.create_read_concatenation()
        if read_val is not None:
            decoder = (paddr_offs == offs) if paddr_offs is not None else 1
            read_map[offs] = (decoder, read_val)
    if len(read_map) > 0:
        bus.prdata <<= Reg(SelectOne(*chain.from_iterable(read_map.values())))
    for offs, reg in regs.items():
        decoder = (paddr_offs == offs) if paddr_offs is not None else 1
        read_pulse  = read_strobe  & decoder
        write_pulse = write_strobe & decoder
        if reg.read_pulse is not None:
            reg.read_pulse <<= read_pulse
        if reg.write_pulse is not None:
            reg.write_pulse <<= write_pulse
        reg.create_reg(bus.pwdata, write_pulse)

