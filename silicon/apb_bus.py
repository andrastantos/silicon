# Contains a simple generic definition for the APB bus.
#     https://developer.arm.com/documentation/ihi0024/latest/

from dataclasses import dataclass
from collections import OrderedDict
from enum import Enum as PyEnum
from typing import Dict

from .composite import Interface, Reverse, GenericMember
from .number import logic
from .net_type import NetType
from .module import GenericModule
from .auto_input import ClkPort, RstPort
from .port import Input, Output, Junction, Wire
from .exceptions import SyntaxErrorException
from .number import Unsigned
from .primitives import Reg

class ApbBaseIf(Interface):

    #APB signalling
    #
    #            <-- read -->      <-- write ->
    #    CLK     \__/^^\__/^^\__/^^\__/^^\__/^^\__/^^\__/
    #    psel    ___/^^^^^^^^^^^\_____/^^^^^^^^^^^\______
    #    penable _________/^^^^^\___________/^^^^^\______
    #    pready  ---------/^^^^^\-----------/^^^^^\------
    #    pwrite  ---/^^^^^^^^^^^\-----\___________/------
    #    paddr   ---<===========>-----<===========>------
    #    prdata  ---------<=====>------------------------
    #    pwdata  ---------------------<===========>------

    pwrite = logic
    psel = logic
    penable = logic
    pready = Reverse(logic)



_apb_if_cache = {}

def ApbIf(data_type: NetType, addr_type: NetType = None) -> type:
    """Creates and returns an APB interface type for the specified datatype.

    :param data_type: The NetType for the prdata and pwdata members of the APB interface

    :return: Returns an ApbBaseIf sub-class with the properly typed prdata and pwdata members.
    """

    key = (data_type, addr_type)
    if key in _apb_if_cache:
        return _apb_if_cache[key]
    type_name = f"ApbIf_D[{data_type.get_type_name()}]" if addr_type is None else f"ApbIf_D[{data_type.get_type_name()}]_A[{addr_type.get_type_name()}]"
    ApbIfType = type(type_name, (ApbBaseIf,), {})
    ApbIfType.add_member("pwdata", data_type)
    ApbIfType.add_member("prdata", Reverse(data_type))
    if addr_type is not None:
        ApbIfType.add_member("paddr", addr_type)
    else:
        ApbIfType.add_member("paddr", GenericMember)
    _apb_if_cache[key] = ApbIfType
    return ApbIfType


class ApbReg(GenericModule):
    clk = ClkPort()
    rst = RstPort()

    write_strobe = Output(logic)
    read_strobe = Output(logic)

    apb_bus = Input()

    def construct(self, address=None):
        self.address = address
        self.fields: Dict[str, 'ApbReg.FieldDesc'] = OrderedDict()
        self.bitmask = []
        #self.in_add_field = False

    class Kind(PyEnum):
        ctrl = 0,
        stat = 1,
        both = 2

    @dataclass
    class FieldDesc(object):
        high_bit: int
        low_bit: int
        ctrl_port: Junction = None
        stat_port: Junction = None

    def add_field(self, name, high_bit, low_bit, kind: 'ApbReg.Kind', net_type: NetType = None):
        if name in self.fields:
            raise SyntaxErrorException(f"Field name {name} is already used")
        if high_bit < low_bit:
            raise SyntaxErrorException(f"Bit-range higher ({high_bit}) end must higher then the lower end ({low_bit})")

        desc = ApbReg.FieldDesc(high_bit, low_bit)
        while len(self.bitmask) <= high_bit:
            self.bitmask.append(0)

        width = high_bit - low_bit + 1
        for ibit in range(low_bit, high_bit+1):
            if self.bitmask[ibit] == 1:
                raise SyntaxErrorException(f"Bit {ibit} is already used")
            self.bitmask[ibit] = 1
        #with ScopedAttr(self, "in_add_field", True):
        if net_type is None:
            net_type = Unsigned(width)
        if kind == ApbReg.Kind.stat or kind == ApbReg.Kind.both:
            stat_port = self.create_named_port(f"{name}_stat", port_type=Input, net_type=net_type)
            desc.stat_port = stat_port
        if kind == ApbReg.Kind.ctrl or kind == ApbReg.Kind.both:
            ctrl_port = self.create_named_port(f"{name}_ctrl", port_type=Output, net_type=net_type)
            desc.ctrl_port = ctrl_port
        self.fields[name] = desc
        return desc

    def body(self):
        if self.address is not None:
            reg_decode = self.apb_bus.paddr == self.address
        else:
            reg_decode = 1

        write_strobe = self.apb_bus.psel & self.apb_bus.pwrite & self.apb_bus.penable & reg_decode
        self.write_strobe <<= write_strobe
        read_strobe = self.apb_bus.psel & ~self.apb_bus.pwrite & self.apb_bus.penable & reg_decode
        self.read_strobe <<= read_strobe

        self.apb_bus.pready <<= 1

        read_value = Wire(self.apb_bus.prdata.get_net_type())
        for field in self.fields.values():
            for fbit, rbit in enumerate(range(field.low_bit, field.high_bit+1)):
                read_value[rbit] <<= field.stat_port[fbit] if field.stat_port is not None else field.ctrl_port[fbit]
            if field.ctrl_port is not None:
                field.ctrl_port <<= Reg(self.apb_bus.pwdata[field.high_bit:field.low_bit], clock_en=write_strobe)
        for rbit, used in enumerate(self.bitmask):
            if used == 0:
                read_value[rbit] <<= 0
        for idx in range(len(self.bitmask), self.apb_bus.prdata.get_net_type().get_num_bits()):
            read_value[idx] <<= 0
        self.apb_bus.prdata <<= read_value
