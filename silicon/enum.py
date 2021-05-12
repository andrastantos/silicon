from .number import Number, val_to_sim
from enum import Enum as PyEnum
from enum import EnumMeta
#from enum import IntEnum as PyIntEnum
from typing import Tuple, Union, Optional, Any, Sequence, Generator
from .net_type import NetType
from .utils import first, TSimEvent
from .exceptions import SimulationException, SyntaxErrorException
from .netlist import Netlist
from .module import Module, InlineBlock, InlineExpression
from .port import Input, Output, Junction

# Python Enums are weird to say the least: Even though you inherit from Enum, the actual enum *type* is EnumMeta. The *values* of the enum become
# the type of the class you subclass from Enum. As such, it's not possible (or at least very hard) to mix-in NetType with EnumMeta. So, for now
# we're going to simply reference the enum in the constructor (even though it's a bit uglier)

# NOTE: SV enums auto-convert to int, but not the other way around: ints would need to be explicitly converted to enums, even if the value exists in the enumeration.

class Enum(Number):
    def __init__(self, base_type: EnumMeta):
        self.base_type = base_type
        super().__init__(min_val = min(e.value for e in base_type), max_val = max(e.value for e in base_type))

        from .constant import const_convert_lookup, sim_convert_lookup
        enum_type = type(first(base_type))
        const_convert_lookup[enum_type] = enum_to_const
        sim_convert_lookup[enum_type] = Enum.val_to_sim

        #self.possible_values = set(e.value for e in base_type)

    vcd_type: str = 'string'

    class EnumConverter(object):
        def __init__(self, value):
            self.value = value
        def __int__(self):
            return self.value.value
        def __add__(self, other):
            return int(self) + int(other)
        def __sub__(self, other):
            return int(self) - int(other)
        def __mul__(self, other: Any) -> Any:
            return int(self) * int(other)
        def __floordiv__(self, other: Any) -> Any:
            return int(self) // int(other)
        def __mod__(self, other: Any) -> Any:
            return int(self) % int(other)
        def __divmod__(self, other: Any) -> Any:
            return divmod(int(self), int(other))
        def __pow__(self, other: Any, modulo = None) -> Any:
            return pow(int(self), int(other), modulo)
        def __lshift__(self, other: Any) -> Any:
            return int(self) << int(other)
        def __rshift__(self, other: Any) -> Any:
            return int(self) >> int(other)
        def __and__(self, other: Any) -> Any:
            return int(self) & int(other)
        def __xor__(self, other: Any) -> Any:
            return int(self) ^ int(other)
        def __or__(self, other: Any) -> Any:
            return int(self) | int(other)
        def __truediv__(self, other: Any) -> Any:
            return int(self) / int(other)

        def __radd__(self, other: Any) -> Any:
            return int(other) + int(self)
        def __rsub__(self, other: Any) -> Any:
            return int(other) - int(self)
        def __rmul__(self, other: Any) -> Any:
            return int(other) * int(self)
        def __rtruediv__(self, other: Any) -> Any:
            return int(other) / int(self)
        def __rfloordiv__(self, other: Any) -> Any:
            return int(other) // int(self)
        def __rmod__(self, other: Any) -> Any:
            return int(other) % int(self)
        def __rdivmod__(self, other: Any) -> Any:
            return divmod(int(other), int(self))
        def __rpow__(self, other: Any, modulo: Any = None) -> Any:
            return pow(int(other), int(self), modulo)
        def __rlshift__(self, other: Any) -> Any:
            return int(other) << int(self)
        def __rrshift__(self, other: Any) -> Any:
            return int(other) >> int(self)
        def __rand__(self, other: Any) -> Any:
            return int(other) & int(self)
        def __rxor__(self, other: Any) -> Any:
            return int(other) ^ int(self)
        def __ror__(self, other: Any) -> Any:
            return int(other) | int(self)

        def __neg__(self) -> Any:
            return -int(self)
        def __pos__(self) -> Any:
            return +int(self)
        def __abs__(self) -> Any:
            return abs(int(self))
        def __invert__(self) -> Any:
            return ~int(self)

        def __bool__(self) -> bool:
            return bool(int(self))
        def __lt__(self, other: Any) -> bool:
            return int(self) < int(other)
        def __le__(self, other: Any) -> bool:
            return int(self) <= int(other)
        def __eq__(self, other: Any) -> bool:
            return int(self) == int(other)
        def __ne__(self, other: Any) -> bool:
            return int(self) != int(other)
        def __gt__(self, other: Any) -> bool:
            return int(self) > int(other)
        def __ge__(self, other: Any) -> bool:
            return int(self) >= int(other)

    @staticmethod
    def val_to_sim(val):
        return Enum.EnumConverter(val)

    def __str__(self) -> str:
        return f"Enum({self.get_type_name()})"

    def __repr__(self) -> str:
        return f"Enum({self.get_type_name()})"

    def get_type_name(self) -> Optional[str]:
        """
        Returns a unique name for the type. This name is used to identify the type, in other words, if two type object instances return the same string from get_type_name, they are considered to be the same type.
        Gets frequently overridden in subclasses to provide unique behavior.

        This function is only used to call 'generate' on types that need it (such as interfaces).
        """
        return self.base_type.__name__

    def generate(self, netlist: Netlist, back_end: 'BackEnd') -> str:
        base_type = super().generate_type_ref(back_end)
        values = ",\n".join(f"{e.name}={e.value}" for e in self.base_type)
        return f"typedef enum {base_type} {{\n{back_end.indent(values)}\n}} {self.get_type_name()};"
    def generate_type_ref(self, back_end: 'BackEnd') -> str:
        return self.get_type_name()

    # Numbers implementation seems to be sufficient
    #def generate_net_type_ref(self, for_junction: 'Junction', back_end: 'BackEnd') -> str:
    def generate_const_val(self, value: Optional[PyEnum], back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return value.name

    def convert_to_vcd_type(self, value: Optional[Union['Enum', 'EnumConverter']]) -> Any:
        if value is None:
            return None
        return value.value.name

    from .module import GenericModule
    class EnumAdaptor(GenericModule):
        def construct(self, input_type: 'Number', output_type: 'Enum') -> None:
            if input_type.is_abstract():
                raise SyntaxErrorException("Cannot adapt to numbers from abstract types")
            if output_type.is_abstract():
                raise SyntaxErrorException("Cannot adapt to abstract number types")
            if not isinstance(input_type, Number):
                raise SyntaxErrorException("Can only adapt the size of numbers")
            if not isinstance(output_type, Enum):
                raise SyntaxErrorException("Can only adapt the size of numbers")
            self.input_port = Input(input_type)
            self.output_port = Output(output_type)
        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))
        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"

            rhs_name, _ = self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), allow_expression = True)
            ret_val = f"{self.output_port.get_net_type().get_type_name()}'({rhs_name})"
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
                        raise SimulationException(f"Enum {self.output_port.get_net_type().get_type_name()} cannot be assigned a numberic value {self.input_port.sim_value}.", self)
        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

    def adapt_from(self, input: 'Junction', implicit: bool, force: bool) -> 'Junction':
        input_type = input.get_net_type()
        if not isinstance(input_type, Enum):
            if implicit:
                return None
            if not isinstance(input_type, Number):
                return None
            return Enum.EnumAdaptor(input_type, self)(input)
        # Not only we have to have both junctions being Enums, we have to make sure they're instances of the *same* Enum...
        if self.base_type is not input_type.base_type:
            if implicit:
                return None
            return Enum.EnumAdaptor(input_type, self)(input)
        return input

    # For now, these we'll leave intact, but that means that enums are closer to Numbers we might want them to be....
    # We might also open up a bunch of cases where we silently should convert to Numbers, but we don't
    #def get_iterator(self, parent_junction: Junction) -> Any:
    #def get_slice(self, key: Any, junction: Junction) -> Any:
    #def set_slice(self, key: Any, value: Any, junction: Junction) -> None:
    #def resolve_key_sequence_for_get(self, keys: Sequence[Any]) -> Any:
    #    raise SyntaxErrorException("Enum types don't support subscription or member accesses")
    def get_default_sim_value(self) -> Any:
        return first(self.base_type)
    def validate_sim_value(self, sim_value: Any, parent_junction: 'Junction') -> Any:
        if sim_value is None:
            return sim_value
        if not isinstance(sim_value, Enum.EnumConverter):
            raise SimulationException(f"Value {sim_value} of type {type(sim_value)} is not valid for an Enum type {self.get_type_name()}", parent_junction)
        elif sim_value.value in self.base_type:
            return sim_value
        else:
            raise SimulationException(f"Value {sim_value.value} can't be represented by Enum type {self.get_type_name()}", parent_junction)
    
    @classmethod
    def result_type(cls, net_types: Sequence[Optional['NetType']], operation: str) -> 'NetType':
        # If we're SELECT-ing from all Enum junctions of the same underlying PyEnum, go with that, otherwise revert to Number.
        if operation == "SELECT":
            if all(isinstance(net_type, Enum) for net_type in net_types):
                enum_type = first(net_types).base_type
                if all(net_type.base_type is enum_type for net_type in net_types):
                    return first(net_types)
        return super().result_type(net_types, operation)

    def __eq__(self, other):
        return self is other or type(self) is type(other)

def enum_to_const(value: Enum) -> Tuple[NetType, Enum]:
    return Enum(type(value)), value


from .constant import const_convert_lookup, sim_convert_lookup
const_convert_lookup[PyEnum] = enum_to_const
#sim_convert_lookup[Enum] = val_to_sim
sim_convert_lookup[Enum.EnumConverter] = lambda enum_converter: enum_converter

