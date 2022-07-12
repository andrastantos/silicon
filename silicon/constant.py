from typing import Tuple, Union, Any, Dict, Set, Optional, Callable, Type, Generator

from .net_type import NetType
from .module import Module, GenericModule, InlineBlock, InlineExpression
from .port import Input, Output
from .utils import TSimEvent
from .exceptions import SyntaxErrorException
from inspect import getmro

const_to_rtl_lookup: Dict[NetType, Callable] = {}
const_convert_lookup: Dict[Type, Union[Callable, NetType]] = {}

class Constant(object):
    def __init__(self, net_type: NetType, value: Any) -> None:
        self.net_type = net_type
        self.value = value
    def __str__(self):
        return str(self.value)

class ConstantModule(GenericModule):
    def construct(self, constant: Constant) -> None:

        self.output_port = Output(constant.net_type)
        self.output_port.set_parent_module(self)
        self.constant = constant

    def generate_const_val(self, back_end: 'BackEnd') -> str:
        net_type = self.output_port.get_net_type()
        value = self.constant.value
        if NetType in const_to_rtl_lookup:
            return const_to_rtl_lookup[NetType](value, back_end)
        if hasattr(net_type, "generate_const_val"):
            return net_type.generate_const_val(value, back_end)
        if hasattr(self.constant, "generate_const_val"):
            return self.constant.generate_const_val(back_end)
        assert False, "Don't know how to convert constant value {} into RTL for port type {}".format(value, net_type)

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        assert len(self.get_outputs()) == 1
        yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))

    def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        ret_val = f"{self.generate_const_val(back_end)}"
        return ret_val, 0

    def simulate(self) -> TSimEvent:
        self.output_port <<= self.constant.value

    def is_combinational(self) -> bool:
        """
        Returns True if the module is purely combinational, False otherwise
        """
        return True

def get_net_type_for_const(value: Any) -> Optional[NetType]:
    if isinstance(value, Constant):
        return value.net_type
    for base in getmro(type(value)):
        if base in const_convert_lookup:
            # Returns a tuple with index 0 being the net type
            return const_convert_lookup[base](value, None)[0]

    return None


def _const(value: Any, type_hint: Optional[NetType] = None) -> Optional[Constant]:
    if isinstance(value, Constant):
        return value
    for base in getmro(type(value)):
        if base in const_convert_lookup:
            return Constant(*const_convert_lookup[base](value, type_hint))

    raise SyntaxErrorException(f"Don't know how to create Constant from value {value}")

def const(value: Any) -> Constant:
    return _const(value, type_hint=None)

class NoneType(NetType):
    @staticmethod
    def Key():
        raise SyntaxErrorException("None type cannot be used as key")

#def None_to_const(value: None) -> Tuple[None, None]:
#    return None, None

#const_convert_lookup[type(None)] = None_to_const
