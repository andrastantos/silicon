from typing import Tuple, Union, Any, Dict, Set, Optional, Callable, Generator, Type

from .net_type import NetType
from .tracer import no_trace
from .module import Module, InlineBlock, InlineExpression
from .exceptions import SyntaxErrorException
from .port import Junction, Input, Output
from .utils import first

class VectorBase(NetType):
    """
    A vector base-class that supports all the common vector constructs that don't require
    actual value representation. That is to say, this base-type has no simulation functionality.

    Sub-classes of this type can add value represtation and simulation support. There are two
    main sub-classes of VectorBase:
    1. Vector, which is a vector of arbitrary elements and defers most simulation activity
       to the underlying element type.
    2. Number, which is a range-tracking numerical type that forms the base of almost all other types,
       including logic and binary vectors.

    IMPORTANT NOTE:
    the length member controls the number of elements in the vector. This can be set to None to signify
    an indeterminate vector length. These types cannot be instantiated as ports, but can be used as
    prototypes for fully specified vector types with a valid length field, which can.
    
    In this regard, vector type are sort-of template types, which can be fully instantiated by specifying their length
    """
    from .module import GenericModule
    from .port import Input, Output

    class Key(object):
        def __init__(self, thing: Any):
            if isinstance(thing, slice):
                self.start = thing.start
                self.stop = thing.stop
                assert thing.start < thing.stop, "Reversed ranges are not supported"
                assert thing.start >= 0, "FIXME: negative ranges are not supported for the moment"
                assert thing.step is None or thing.step == 1, "Don't support non-continous slices"
            elif isinstance(thing, int):
                self.start = thing
                self.stop = thing + 1
            else:
                assert False, "Vector only supports integer indices or continous ranges. Key [{}] is not supported.".format(thing)


    class VectorAccessor(GenericModule):
        def construct(self, member: Any, vector: 'Vector') -> None:
            from .port import Input, Output

            self.length = vector.length
            self.element_type = vector.element_type
            self.key = vector.get_member_key(member)
            self.input_port = Input(vector)
            self.input_port.set_parent_module(self)
            self.output_port = Output(vector.get_member_type(member))
            self.output_port.set_parent_module(self)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert self.input_port is not None, "Can't generate RTL for vector accessor with no inputs"
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end)
            if self.key.stop -1 == self.key.start:
                ret_val += "\n\tassign output_port = input_port[{}];\n".format(self.key.start)
            else:
                ret_val += "\n\tassign output_port = input_port[{}:{}];\n".format(self.key.stop-1, self.key.start)
            ret_val += "endmodule\n\n\n"
            return ret_val
        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineExpression, None, None]:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))
        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"

            op_precedence = back_end.get_operator_precedence("[]")
            rhs_name, rhs_precedence = target_namespace.get_rhs_expression_for_junction(self.input_port, back_end, target_namespace)
            if op_precedence < rhs_precedence:
                rhs_name = "(" + rhs_name + ")"
            if self.key.stop -1 == self.key.start:
                return f"{rhs_name}[{self.key.start}]", back_end.get_operator_precedence("[]")
            else:
                return f"{rhs_name}[{self.key.stop-1}:{self.key.start}]", back_end.get_operator_precedence("[]")

    def set_length(self, length: int) -> None:
        if self.length is not None:
            raise SyntaxErrorException("Cannot set the length of a fully specified vector")
        self.length = length

    class Concatenator(GenericModule):
        def construct(self, vector_type: NetType) -> None:
            if not vector_type.is_abstract():
                raise SyntaxErrorException("Cannot only create Concatenator for abstract vector types")
            self.vector_type = vector_type
            self.output_length = 0
        def create_named_port(self, name: str, net_type: NetType) -> None:
            assert False
            from .port import Input

            if not name.startswith("input_port_"):
                return

            if not self.vector_type.is_compatible(net_type):
                raise SyntaxErrorException(f"Can't bind port of type {net_type} to vector combiner with vector type of {self.vector_type}")
            assert not is_inside, "Can't create port from the inside for vector combiner"
            assert not self.is_interface_frozen(), "Can't assign new ports to vector combiner after input port list is frozen (such as after output has been bound)"
            from .port import Input
            input_port = Input(net_type)
            setattr(self, name, input_port)
        def create_positional_port(self, idx: int) -> None:
            assert False
            self.create_named_port("input_port_{}".format(idx), net_type)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert len(self.inputs) != 0, "Can't generate RTL for vector combiner with no inputs"
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end)
            ret_val += "\n\tassign output_port = {"
            first_input = True
            for input in self.inputs.values():
                if not first_input:
                    ret_val += ", "
                rhs_name, _ = target_namespace.get_rhs_expression_for_junction(input, back_end)
                ret_val += rhs_name
                first_input = False
            ret_val += "};\n"
            ret_val += "endmodule\n\n\n"
            return ret_val
        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))
        def generate_inline_expression(self, back_end: 'BackEnd') -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"

            if len(self.inputs) == 0:
                raise SyntaxErrorException("Can't combine 0 vector elements")
            elif len(self.inputs) == 1:
                return target_namespace.get_rhs_expression_for_junction(first(self.inputs.values()), back_end, target_namespace)
            else:
                ret_val = "{"
                first_input = True
                for input in self.inputs.values():
                    if not first_input:
                        ret_val += ", "
                    rhs_name, _ = target_namespace.get_rhs_expression_for_junction(input, back_end)
                    ret_val += rhs_name
                    first_input = False
                ret_val += "}"
                return ret_val, back_end.get_operator_precedence("{}")

    def __init__(self, element_type: NetType, length: Optional[int] = None):
        self._element_type = element_type
        self.length = length
        super().__init__()
    
    def generate_type_ref(self, back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        assert self.length is not None, "Can't generate RTL for vector with indeterminate length"
        return f"{self.element_type.generate_type_ref(back_end)} [{self.length - 1}:0]"

    def generate_net_type_ref(self, for_port: 'Junction', back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return f"{for_port.generate_junction_ref(back_end)} {self.generate_type_ref(back_end)}"

    def is_compatible(self, other) -> bool:
        # We compare sink (self) to source (other),
        # By default, two port types are compatible if their classes are the same
        if type(self) != type(other):
            return False
        if not self.element_type.is_compatible(other.element_type):
            return False
        if self.length is None:
            return True
        if self.length != other.length:
            return False
        return True
    
    def bind_to_port(self, parent_junction: 'port') -> 'NetType':
        assert False, "This doesn't exist anymore!!!"
        """
        Binds a copy of the type to the specified port, overriding member access to support struct-style accesses
        """
        # Injected __getattr__ and __setattr__ implementations
        def instance_get_member(self, member: Any) -> 'Junction':
            accessor = Vector.VectorAccessor(member, self.net_type)
            return accessor(self)
        def instance_set_member(self, member: Any, value: Any) -> None:
            assert hasattr(self.net_type, "get_member_key"), "Can't access elements of non-composite types"
            assert hasattr(self.net_type, "get_member_type")
            key = self.net_type.get_member_key(member)
            from .module import convert_to_junction
            self.add_source(convert_to_junction(value), key)

        # We need to be a bit shifty here: __getattr__ and __setattr__ only work if it's set on the
        # class level, yet we want per-instance behavior. So we'll have to set the class-level
        # methods (which apply to all ports) to something benign that only trampolines to the instance
        # if the proper methods are set on the instance as well - which will only be so for struct-ports.
        from types import MethodType
        new_net_type = super().bind_to_port(parent_junction)
        parent_junction.get_vector_member = MethodType(instance_get_member, parent_junction)
        parent_junction.set_vector_member = MethodType(instance_set_member, parent_junction)
        return new_net_type
    # For member access, simply return the slice definition.
    # TODO: member definitions are not unique in this case (for example for a vector of 8 [7] and [-1] refer to the same element)
    #       For now, we're going to restrict ourselves to something that's simple...
    def get_member_key(self, member: Any) -> 'Key':
        ret_val = Vector.Key(member)
        if self.length is None:
            raise SyntaxErrorException("Can't access elements of a vector of indeterminate length")
        if ret_val.start >= self.length or ret_val.stop -1 >= self.length:
            raise SyntaxErrorException(f"Can't access members outside of vector length {self.length}")
        return ret_val
    def get_member_type(self, member: Any) -> NetType:
        key = self.get_member_key(member)
        if key.start == key.stop-1:
            return self.element_type
        else:
            return type(self)(element_type = self.element_type, length = member.stop - member.start)

    def __overlap__(self, range1 : 'Key', range2: 'Key') -> bool:
        assert range1.start < range1.stop
        assert range2.start < range2.stop
        if range1.start >= range2.stop:
            return False
        if range2.start >= range1.stop:
            return False
        return True
    def is_key_allowed_as_source(self, key: 'Key', existing_keys: Dict['Key', 'Junction']) -> bool:
        if key in existing_keys:
            return False
        for existing_key in existing_keys.keys():
            if self.__overlap__(key, existing_key):
                return False
        return True
    def is_key_allowed_as_sink(self, key: 'Key', existing_keys: Dict['Key', Set['Junction']]) -> bool:
        return True
    def sort_source_keys(self, keys: Dict['Key', 'Junction'], back_end: Optional['BackEnd']) -> Tuple['Key']:
        """ Sort the set of blobs as required by the back-end """
        assert back_end is None or back_end.language == "SystemVerilog"
        from operator import attrgetter
        keys = list(key for key in keys.keys())
        if len(keys) == 1:
            return tuple(keys)
        sorted_keys = tuple(sorted(keys, key=attrgetter('start'), reverse=True))
        return sorted_keys
    def sort_sink_keys(self, keys: Dict['Key', Set['Junction']], back_end: 'BackEnd') -> Tuple['Key']:
        """ Sort the set of blobs as required by the back-end """
        return self.sort_source_keys(keys, back_end)

    def compose_fill_expression(self, key: range, back_end: 'BackEnd') -> Optional[str]:
        """
        Returns a fill expression for the specitied range of the vector, or None if no fill is needed
        """
        assert key.step == 1 or key.step == -1
        x_len = abs(key.stop - key.start) * self.element_type.get_num_bits()
        return f"{x_len}'bX"
    def compose_sources_expression(self, parent_junction: Junction, back_end: 'BackEnd') -> Tuple[str, int]:
        assert False
        # No source: return a X-assignment
        assert back_end.language == "SystemVerilog"
        if self.length is None:
            raise SyntaxErrorException("Can't create assignment to vector of indeterminate length")
        if len(parent_junction.sources) == 0:
            return self.compose_fill_expression(range(self.length), back_end), 0
        if len(parent_junction.sources) == 1:
            source = first(parent_junction.sources.values())
            if source.net_type.length > self.length:
                raise SyntaxErrorException(f"Source port length {source.net_type.length} is greater than sink port length {self.length}. But where???")
            elif source.net_type.length == self.length:
                return target_namespace.get_rhs_expression_for_junction(source, back_end)
        sorted_keys = self.sort_source_keys(parent_junction.sources, back_end)
        rtl_parts = []
        last_top_idx = self.length
        sub_port_precedence = None
        for sub_port_key in sorted_keys:
            # If there was a direct assignment, but the lengths don't match, we end up with a single key that's None...
            if sub_port_key is None:
                assert len(sorted_keys) == 1
                sub_port_key_range = range(0, parent_junction.sources[sub_port_key].net_type.length)
            else:
                sub_port_key_range = sub_port_key
            current_top_idx = sub_port_key_range.stop - 1
            assert current_top_idx < last_top_idx
            if current_top_idx < last_top_idx - 1:
                fill_expr = self.compose_fill_expression(range(last_top_idx - 1, current_top_idx, -1), back_end)
                if fill_expr is not None:
                    rtl_parts.append(fill_expr)
                    sub_port_precedence = 0
            last_top_idx = sub_port_key_range.start
            sub_port = parent_junction.sources[sub_port_key]
            sub_port_name, sub_port_precedence = target_namespace.get_rhs_expression_for_junction(sub_port, back_end)
            rtl_parts.append(sub_port_name)
        if last_top_idx > 0:
            fill_expr = self.compose_fill_expression(range(last_top_idx), back_end)
            assert fill_expr is not None
            rtl_parts.append(fill_expr)
            sub_port_precedence = 0
        if len(rtl_parts) == 1:
            assert sub_port_precedence is not None
            return rtl_parts[0], sub_port_precedence
        ret_val = "{" + ", ".join(rtl_parts) + "}"
        return ret_val, back_end.get_operator_precedence("{}")
    def get_num_bits(self) -> int:
        return self.length * self.element_type.get_num_bits()
    @property
    def element_type(self):
        return self._element_type
    @property
    def element_count(self):
        return self.length
    @property
    def sim_value(self, parent_junction: Junction) -> Any:
        assert False, "This is way more complicated than this: we'll have to base the code on compose_source_assignment above!"
        sim_state = parent_junction.sim_state
        return sim_state.value
    def is_abstract(self) -> bool:
        """
        Returns True if the type is abstract, that is it can't be the type of an actual Junction.
        """
        return self.length is None


class Vector(VectorBase):
    def get_preferred_vector_type(self) -> Type:
        """
        Returns the preferred vector type for this type.

        For actual vector types, this is going to be self, most likely.
        The default implementation simply return Vector.

        NOTE: when returning a type, the element type of the returned vector need not to be set.
        """
        return type(self)(element_type = self.element_type)
    def adapt_from(self, input: 'Junction', implicit: bool) -> 'Junction':
        if not self.element_type.is_compatible(input.element_type):
            return None
        if input.is_abstract():
            return None
        if not self.is_abstract() and self.element_count < input.element_count:
            return None
        # For now, adaptation of this kind is simple: really just return the input.
        # TODO: we probably want to do more complex adaptors in the future because not all back-ends are as loosy-goosy as SystemVerilog
        return input