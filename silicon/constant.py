from typing import Tuple, Union, Any, Dict, Set, Optional, Callable, Type, Generator

from .net_type import NetType
from .module import Module, GenericModule, InlineBlock, InlineExpression
from .port import Input, Output
from .utils import TSimEvent, Context
from .exceptions import SyntaxErrorException, AdaptTypeError
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

class NoneNetType(NetType):
    @staticmethod
    def Key():
        raise SyntaxErrorException("None type cannot be used as key")
    @classmethod
    def generate_const_val(cls, value: Optional[int], back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        # This is a hack. According to IEEE Std 1800-2012, the value of a signed expression where the sign-bit is X gets
        # sign-extended with X-es to however many bits needed.
        return "$signed(1'bX)"

    @classmethod
    def get_rhs_expression(cls, for_junction: 'Junction', back_end: 'BackEnd', target_namespace: Module, outer_precedence: Optional[int] = None, allow_expression: bool = True) -> Tuple[str, int]:
        xnet = target_namespace._impl.netlist.get_xnet_for_junction(for_junction)
        expr, prec = xnet.get_rhs_expression(target_namespace, back_end, allow_expression)
        if outer_precedence is not None and prec > outer_precedence:
            return f"({expr})", back_end.get_operator_precedence("()")
        else:
            return expr, prec

    @classmethod
    def adapt_from(cls, input: Any, implicit: bool, force: bool, allow_memberwise_adapt: bool) -> Any:
        context = Context.current()

        if context == Context.simulation:
            if input is None:
                return None
            raise AdaptTypeError
        elif context == Context.elaboration:
            raise AdaptTypeError

    @classmethod
    def get_num_bits(cls) -> int:
        return 1

    class ToType(GenericModule):
        input_port = Input()
        output_port = Output()
        def construct(self, output_type: NetType):
            self.output_port.set_net_type(output_type)

        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))

        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"

            return self.output_port.get_net_type().get_unconnected_value(back_end), 0

        def simulate(self) -> TSimEvent:
            self.output_port <<= None

        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

    @classmethod
    def adapt_to(cls, output_type: 'NetType', input: 'Junction', implicit: bool, force: bool, allow_memberwise_adapt: bool) -> Optional['Junction']:
        assert input.get_net_type() is cls
        if output_type is cls:
            return input

        context = Context.current()

        if context == Context.simulation:
            return None
        elif context == Context.elaboration:
            return NoneNetType.ToType(output_type)(input)

    vcd_type: str = 'wire'

    @classmethod
    def convert_to_vcd_type(cls, value: Any) -> Any:
        return 'X'

    @classmethod
    def get_default_sim_value(cls) -> Any:
        return None

    @classmethod
    def get_iterator(cls, parent_junction: 'Junction') -> Any:
        class Iterator(object):
            def __init__(self):
                pass
            def __next__(self):
                raise StopIteration

        return Iterator()

    @classmethod
    def generate_type_ref(cls, back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return "/*X*/ logic"

    @classmethod
    def generate_net_type_ref(cls, for_junction: 'Junction', back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return f"{for_junction.generate_junction_ref(back_end)} {cls.generate_type_ref(back_end)}"

def None_to_const(value: None, type_hint: Optional[NetType] = None) -> Tuple[NetType, None]:
    return NoneNetType, None

const_convert_lookup[type(None)] = None_to_const
