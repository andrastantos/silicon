from .number import Number, is_number, NumberMeta
from enum import Enum, EnumMeta
from typing import Tuple, Union, Optional, Any, Sequence, Generator
from .net_type import NetType
from .utils import first, TSimEvent, Context, is_junction_base
from .exceptions import SimulationException, SyntaxErrorException, AdaptTypeError
from .netlist import Netlist
from .module import Module, InlineBlock, InlineExpression
from .port import Input, Output, Junction
from .constant import NoneNetType

# Python Enums are weird to say the least: Even though you inherit from Enum, the actual enum *type* is EnumMeta. The *values* of the enum become
# the type of the class you subclass from Enum. As such, it's not possible (or at least very hard) to mix-in NetType with EnumMeta. So, for now
# we're going to simply reference the enum in the constructor (even though it's a bit uglier)

# NOTE: SV enums auto-convert to int, but not the other way around: ints would need to be explicitly converted to enums, even if the value exists in the enumeration.

def is_enum(thing: Any) -> bool:
    try:
        return issubclass(thing, EnumNet.Instance)
    except TypeError:
        return False

class EnumTypeMeta(NumberMeta): pass
class EnumNet(Number):
    @classmethod
    def construct(cls, net_type, base_type: Optional[EnumMeta] = None):
        assert base_type is not None, "FIXME: we don't support inline Enum declarations at the moment"

        if any(not isinstance(e.value, int) for e in base_type):
            raise SyntaxErrorException("All values for an EnumNet must be integers")

        min_val = min(e.value for e in base_type)
        max_val = max(e.value for e in base_type)

        type_name = f"EnumType_{base_type.__name__}"
        key = base_type
        _ = super().construct(net_type, min_val=min_val, max_val=max_val)
        if net_type is not None:
            net_type.base_type = base_type
        return type_name, key


    class Instance(Number.Instance, metaclass=EnumTypeMeta):
        vcd_type: str = 'string'

        @classmethod
        def get_type_name(cls) -> str:
            # The base_types' name is unique and a much better name to be used in RTL then our own, which has 'EnumType' pre-pended to it.
            return cls.base_type.__name__

        @classmethod
        def generate(cls, netlist: Netlist, back_end: 'BackEnd') -> str:
            assert back_end.language == "SystemVerilog"
            if back_end.support_enum:
                base_type = super().generate_type_ref(back_end)
                const_val_method = super().generate_const_val
                values = ",\n".join(f"{cls.get_type_name()}__{e.name}={const_val_method(e.value, back_end)}" for e in cls.base_type)
                return f"typedef enum {base_type} {{\n{back_end.indent(values)}\n}} {cls.get_type_name()};"
            else:
                ret_val = ""
                for e in cls.base_type:
                    ret_val += f"`define {cls.generate_const_val(e,back_end)[1:]} {super().generate_const_val(e.value, back_end)}\n"
                return ret_val

        @classmethod
        def generate_type_ref(cls, back_end: 'BackEnd') -> str:
            assert back_end.language == "SystemVerilog"
            if back_end.support_enum:
                return cls.get_type_name()
            else:
                return super().generate_type_ref(back_end)

        # Numbers implementation seems to be sufficient
        #def generate_net_type_ref(self, for_junction: 'Junction', back_end: 'BackEnd') -> str:
        @classmethod
        def generate_const_val(cls, value: Optional[Enum], back_end: 'BackEnd') -> str:
            assert back_end.language == "SystemVerilog"
            if back_end.support_enum:
                return f"{cls.get_type_name()}__{value.name}"
            else:
                return f"`{cls.get_type_name()}__{value.name}"

        @classmethod
        def convert_to_vcd_type(cls, value: Optional[Union['EnumNet', 'EnumNet.NetValue']]) -> Any:
            if value is None:
                return None
            return value.enum_value.name

        from .module import GenericModule
        class EnumAdaptor(GenericModule):
            def construct(self, input_type: 'NumberMeta', output_type: 'EnumNet') -> None:
                if not is_number(input_type):
                    raise SyntaxErrorException("Can only adapt the size of numbers")
                if not is_enum(output_type):
                    raise SyntaxErrorException("Can only adapt the size of numbers")
                self.input_port = Input(input_type)
                self.output_port = Output(output_type)
            def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
                yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))
            def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
                assert back_end.language == "SystemVerilog"

                rhs_name, _ = self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), allow_expression = True)
                if back_end.support_enum:
                    ret_val = f"{self.output_port.get_net_type().get_type_name()}'({rhs_name})"
                else:
                    ret_val = ""
                    need_sign_cast = self.input_port.signed and not self.output_port.signed
                    need_int_size_cast = self.input_port.get_net_type().int_length > self.output_port.get_net_type().int_length
                    if need_int_size_cast:
                        ret_val += f"{self.output_port.length}'("
                    rhs_name, precedence = self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type())
                    ret_val += rhs_name
                    if need_int_size_cast:
                        precedence = 0
                        ret_val += ")"
                    if need_sign_cast:
                        precedence = 0
                        if self.output_port.signed:
                            ret_val = back_end.signed_cast(ret_val)
                        else:
                            ret_val = back_end.unsigned_cast(ret_val)
                    return ret_val, precedence
                return ret_val, 0
            def simulate(self) -> TSimEvent:
                while True:
                    yield self.input_port
                    if self.input_port.sim_value is None:
                        self.output_port <<= None
                    else:
                        try:
                            val_as_enum = self.output_port.get_net_type().base_type(self.input_port.sim_value)
                            self.output_port <<= val_as_enum
                        except ValueError:
                            raise SimulationException(f"EnumNet {self.output_port.get_net_type().get_type_name()} cannot be assigned a numberic value {self.input_port.sim_value}.", self)
            def is_combinational(self) -> bool:
                """
                Returns True if the module is purely combinational, False otherwise
                """
                return True

        @classmethod
        def adapt_from(cls, input: Any, implicit: bool, force: bool) -> Any:
            context = Context.current()
            if context == Context.simulation:
                if input is None:
                    return None
                if is_junction_base(input):
                    input = input.sim_value
                elif isinstance(input, cls.base_type):
                    input = EnumNet.NetValue(input)
                elif isinstance(input, EnumNet.NetValue):
                    pass
                elif isinstance(input, (int, Number.NetValue)):
                    if isinstance(input, Number.NetValue):
                        if input.precision != 0:
                            raise SimulationException(f"Can't convert Number {input} to enum type {cls.base_type}. Fractional types are not supported")
                        input = input.value
                    try:
                        input = cls.base_type(input)
                    except ValueError:
                        raise SimulationException(f"Can't convert int value {input} to enum type {cls.base_type}.")
                    input = EnumNet.NetValue(input)
                else:
                    raise SimulationException(f"Don't support input type {type(input)}")
                return input
            elif context == Context.elaboration:
                # We only support adaption from the same type (trivial) or from Numbers, explicitly
                input_type = input.get_net_type()
                if input_type is cls:
                    return input
                if is_number(input_type) and not implicit:
                    return EnumNet.Instance.EnumAdaptor(input_type, cls)(input)
                raise AdaptTypeError

        # For now, these we'll leave intact, but that means that enums are closer to Numbers we might want them to be....
        # We might also open up a bunch of cases where we silently should convert to Numbers, but we don't
        #def get_iterator(self, parent_junction: Junction) -> Any:
        #def get_slice(self, key: Any, junction: Junction) -> Any:
        #def set_slice(self, key: Any, value: Any, junction: Junction) -> None:
        #def resolve_key_sequence_for_get(self, keys: Sequence[Any]) -> Any:
        #    raise SyntaxErrorException("EnumNet doesn't support subscription or member accesses")
        @classmethod
        def get_default_sim_value(cls) -> Any:
            return first(cls.base_type)
        @classmethod
        def validate_sim_value(cls, sim_value: Any, parent_junction: 'Junction') -> Any:
            if sim_value is None:
                return sim_value
            if isinstance(sim_value, EnumNet.NetValue):
                return sim_value
            raise SimulationException(f"Value {sim_value} of type {type(sim_value)} is not valid for EnumNet {cls.get_type_name()}", parent_junction)

        @classmethod
        def sim_constant_to_net_value(cls, value: 'Constant') -> 'EnumNet.NetValue':
            if value.net_type is not cls:
                raise SimulationException(f"Can't assign a constant of type {value.net_type} to a net of type {cls}")
            return EnumNet.NetValue(value.value)


        @classmethod
        def result_type(cls, net_types: Sequence[Optional['NetType']], operation: str) -> 'NetType':
            # If we're SELECT-ing from all EnumNet junctions of the same type, go with that, otherwise revert to Number.
            if operation == "SELECT":
                first_type = first(net_types)
                if all(net_type is first_type or net_type is NoneNetType for net_type in net_types[1:]):
                    return first_type
            return super().result_type(net_types, operation)

    net_type = Instance

    class NetValue(Number.NetValue):
        def __init__(self, value: Optional[Union[EnumMeta,'EnumNet.NetValue']]= None):
            if isinstance(value, EnumNet.NetValue):
                super().__init__(value.value.value)
                self.enum_value = value.value
                return
            if isinstance(value, Enum):
                super().__init__(value.value)
                self.enum_value = value
                return
            else:
                raise SimulationException(f"EnumNet can only be assigned an Enum value")

def enum_to_const(value: EnumNet, type_hint: Optional[NetType]) -> Tuple[NetType, EnumNet]:
    return EnumNet(type(value)), value


from .constant import const_convert_lookup
const_convert_lookup[Enum] = enum_to_const
