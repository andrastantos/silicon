from typing import Tuple, Union, Any, Dict, Set, Optional, Generator, Sequence

from .net_type import NetType, KeyKind
from .netlist import Netlist
from .back_end import BackEnd
from .exceptions import SyntaxErrorException
from .module import Module, GenericModule, InlineExpression, InlineBlock, InlineStatement
from .port import Input, Output, Port, Junction
from .tracer import no_trace
from .utils import TSimEvent, MEMBER_DELIMITER, adapt, cast
from collections import namedtuple, OrderedDict
from copy import copy
from .number import Unsigned, Number
from .port import Wire

import types

# TODO: interface nesting in SystemVerilog is not supported. What to do about that? Maybe it's better if interfaces are modelled as individual wires???

class Reverse(object):
    """
    If added to an interface member, it reverses the direction of the member. Useful for handshake signals.
    """
    def __init__(self, net_type: NetType):
        if not isinstance(net_type, NetType):
            raise SyntaxErrorException(f"Can only reverse Net types. {net_type} is of type {type(net_type)}.")
        self.net_type = net_type

class Composite(NetType):
    """
    A Composite type is the base for both interfaces and structs
    """

    def __init__(self, support_reverse: bool):
        super().__init__()

        self._support_reverse = support_reverse
        self.members = OrderedDict()
        for name in dir(type(self)):
            val = getattr(self,name)
            if isinstance(val, (NetType, Reverse)):
                self.add_member(name, val)

    def add_member(self, name: str, member: Union[NetType, Reverse]) -> None:
        if name in self.members:
            raise SyntaxErrorException(f"Member {name} already exists on composite type {type(self)}")
        if isinstance(member, NetType):
            self.members[name] = (member, False)
        elif isinstance(member, Reverse):
            if self._support_reverse:
                self.members[name] = (member.net_type, True)
            else:
                raise SyntaxErrorException(f"Composite type {type(self)} doesn't support reverse members")
        else:
            raise SyntaxErrorException(f"Composite type members must be either NetTypes or Reverse(NetType)-s. {member} is of type {type(member)}")


    def get_members(self) -> Dict[str, Tuple[Union[NetType, bool]]]:
        return self.members

    def get_all_members(self, prefix: str) -> Dict[str, Tuple[Union[NetType, bool]]]:
        def get_sub_members(composite, prefix: Optional[str], reverse: bool) -> Dict[str, Tuple[Union[NetType, bool]]]:
            def compose_name(prefix: Optional[str], member_name: str) -> str:
                if prefix is None:
                    return member_name
                else:
                    return f"{prefix}{MEMBER_DELIMITER}{member_name}"
            ret_val = OrderedDict()
            for (member_name, (member_type, member_reverse)) in composite.get_members().items():
                if member_type.is_composite():
                    ret_val.update(get_all_members(member_type, compose_name(prefix, member_name), reverse ^ member_reverse))
                else:
                    ret_val[compose_name(prefix, member_name)] = (member_type, member_reverse)
            return ret_val

        return get_sub_members(self, prefix, False)

    def sort_source_keys(self, keys: Dict['Key', 'Junction'], back_end: 'BackEnd') -> Tuple['Key']:
        """ Sort the set of blobs as required by the back-end """
        assert back_end.language == "SystemVerilog"
        return tuple(keys.keys())
    def sort_sink_keys(self, keys: Dict['Key', Set['Junction']], back_end: 'BackEnd') -> Tuple['Key']:
        """ Sort the set of blobs as required by the back-end """
        return self.sort_source_keys(keys, back_end)

    def generate_type_ref(self, back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return str(type(self).__name__)

    def generate_net_type_ref(self, for_port: 'Junction', back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return f"{self.generate_type_ref(back_end)}.{for_port.generate_junction_ref(back_end)}_port"

    def get_num_bits(self) -> int:
        return sum(member_type.get_num_bits() for member_type, member_reverse in self.get_members().values())

    @property
    def vcd_type(self) -> str:
        return None

    def generate_assign(self, sink_name: str, source_expression: str, xnet: 'XNet', back_end: 'BackEnd') -> str:
        # This function cannot be implemented (easily) for composite types. Luckily it should never be called as we never create XNets of composites.
        raise NotImplementedError

    def setup_junction(self, junction: 'Junction') -> None:
        for (member_name, (member_type, member_reverse)) in self.get_members().items():
            junction.create_member_junction(member_name, member_type, member_reverse)
        super().setup_junction(junction)

    def get_unconnected_sim_value(self) -> Any:
        assert False, "Simulation should never enquire about unconnected values of Composites"

    def get_default_sim_value(self) -> Any:
        assert False, "Simulation should never enquire about default values of Composites"

    def __eq__(self, other):
        return self is other or type(self) is type(other)


class Struct(Composite):
    def __init__(self):
        super().__init__(support_reverse = False)

    def __call__(self, *args, **kwargs) -> 'Junction':
        """
        Here we should support the following formats:
        my_wire <<= RGB(r_net, g_net, b_net) # which would assign the three constituents to the appropriate sections
        my_wire <<= RGB(some_other_wire) # which is an explicit type-conversion
        my_wire <<= RGB(5,7,9) # which is a constant assignment and should probably be interpreted as:
        my_wire <<= RGB(Constant(5), Constant(7), Constant(9)) # so, essentially the first format.

        There is a degenerate case if the struct contains only a single member. In that case, we can't determine which format we're using, but
        that's fine: in that case, it doesn't really even matter.

        NOTE: we can use named arguments to make the assignment to elements cleaner:

        my_wire <<= RGB(r=something, g=other, b=a_third_thing)
        """
        if len(args) == 1 and len(kwargs) == 0:
            # This is te explicit type-conversion path
            return super().__call__(self, *args)
        # We're in the element-wise assignment regime
        args_idx = 0
        assigned_names = set()
        # First assign positional arguments, only after exhausting that list, start looking at named ones
        members = self.get_members()
        output_junction = Wire(self)
        for member_name, (member, reversed) in members.items():
            if args_idx < len(args):
                if (reversed):
                    raise SyntaxErrorException("Can't assign to reversed members of a Composite type")
                setattr(output_junction, member_name, args[args_idx])
                assigned_names.add(member_name)
                args_idx += 1
        # Make sure we've actually exhausted all positional arguments
        if args_idx < len(args):
            raise SyntaxErrorException("Too many positional arguments for Struct composition")
        # Go through all named arguments
        for member_name, value in kwargs.items():
            if member_name in assigned_names:
                raise SyntaxErrorException(f"Struct member {member_name} is already assigned")
            member, reversed = members[member_name]
            if (reversed):
                raise SyntaxErrorException("Can't assign to reversed members of a Composite type")
            setattr(output_junction, member_name, value)
            assigned_names.add(member_name)
        return output_junction

    @classmethod
    def result_type(cls, net_types: Sequence[Optional['NetType']], operation: str) -> 'NetType':
        """
        Returns the NetType that can describe any possible result of the specified operation,
        given the paramerters to said operation are (in order) are of the specified types.

        Currently supported operations (strings are used instead of numbers for easier extensibility):
            SELECT
            OR
            AND
            XOR
            SUM
            SUB
            PROD
            SHL
            SHR
            NOT
            NEG
            ABS
        """
        assert len(net_types) > 0
        for net_type in net_types:
            if not isinstance(net_type, Struct) and net_type is not None:
                raise SyntaxErrorException("Can only determine union type if all constituents are Structs")
        if operation == "SELECT":
            start_idx = 0
            first_type = None
            while first_type is None:
                first_type = net_types[start_idx]
                start_idx += 1
                if start_idx == len(net_types):
                    raise SyntaxErrorException(f"Can't determine net type for SELECT: none of the value ports have types")
            for net_type in net_types[start_idx:]:
                if not first_type == net_type:
                    raise SyntaxErrorException("SELECT is only supported on structs of the same type")
            return first_type
        else:
            return super().result_type(net_types, operation) # Will raise an exception.

    def get_lhs_name(self, for_junction: Junction, back_end: BackEnd, target_namespace: Module, allow_implicit: bool=True) -> Optional[str]:
        assert back_end.language == "SystemVerilog"
        ret_val += "{"
        xnets = for_junction._impl.netlist.get_xnets_for_junction(for_junction)
        for idx, (xnet, _) in enumerate(xnets.values()):
            name = xnet.get_lhs_name(target_namespace, allow_implicit=allow_implicit)
            if name is None:
                return None
            if idx != 0:
                ret_val += ", "
            ret_val += f"{name}"
        ret_val += "}"
        return ret_val

    class ToNumber(GenericModule):
        input_port = Input()
        output_port = Output()
        def construct(self, input_type):
            self.input_port.set_net_type(input_type)
            self.output_port.set_net_type(Unsigned(input_type.get_num_bits()))

        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            assert len(self.get_outputs()) == 1
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))

        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"
            ret_val = ""
            op_precedence = back_end.get_operator_precedence("{}")
            ret_val += "{"
            members = self.input_port.get_all_member_junctions(add_self=False)
            for idx, (member) in enumerate(members):
                name, _ = member.get_rhs_expression(back_end, target_namespace)
                if idx != 0:
                    ret_val += ", "
                ret_val += f"{name}"
            ret_val += "}"
            return ret_val, op_precedence

        def simulate(self) -> TSimEvent:
            while True:
                yield self.get_inputs().values()
                xnets = self._impl.netlist.get_xnets_for_junction(self.input_port)
                value = 0
                for xnet, _ in xnets.values():
                    xval = xnet.sim_value
                    if xval is None:
                        value = None
                        break
                    value = value << xnet.get_num_bits()
                    value |= xval
                self.output_port <<= value

        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

    class FromNumber(GenericModule):
        input_port = Input()
        output_port = Output()
        def construct(self, output_type: NetType):
            self.output_port.set_net_type(output_type)
        def body(self):
            in_bits = self.input_port.get_net_type().get_num_bits()
            out_bits = self.output_port.get_net_type().get_num_bits()
            if in_bits > out_bits:
                raise SyntaxErrorException(f"Can't convert Number of {in_bits} bits into a Struct {type(self)}, which needs only {out_bits} bits.")

        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            assert len(self.get_outputs()) == 1
            yield InlineStatement((self.output_port,), self.generate_inline_statement(back_end, target_namespace))

        def generate_inline_statement(self, back_end: 'BackEnd', target_namespace: Module) -> str:
            assert back_end.language == "SystemVerilog"
            ret_val = "assign "
            ret_val += "{"
            xnets = self._impl.netlist.get_xnets_for_junction(self.output_port)
            for idx, (xnet, _) in enumerate(xnets.values()):
                name = xnet.get_lhs_name(target_namespace, allow_implicit=True)
                assert name is not None
                if idx != 0:
                    ret_val += ", "
                ret_val += f"{name}"
            ret_val += "}"
            input_expression, _ = self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type())
            ret_val += f" = {input_expression};"
            return ret_val

        def simulate(self) -> TSimEvent:
            while True:
                yield self.get_inputs().values()
                members = self.output_port.get_all_member_junctions(add_self=False)
                value = self.input_port.sim_value
                for member in reversed(members):
                    if value is None:
                        member <<= None
                    else:
                        bits = member.get_num_bits()
                        member <<= value & ((1 << bits) -1)
                        value = value >> bits

        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

    def adapt_to(self, output_type: 'NetType', input: 'Junction', implicit: bool, force: bool) -> Optional['Junction']:
        assert input.get_net_type() is self
        if output_type == self:
            return input
        # We don't support implicit conversion
        if implicit:
            return None
        # We only support conversion to Numbers
        raw_number = Struct.ToNumber(input.get_net_type())(input)
        if raw_number.get_net_type() == output_type:
            return raw_number
        return cast(raw_number, output_type)

    def adapt_from(self, input: 'Junction', implicit: bool, force: bool) -> 'Junction':
        input_type = input.get_net_type()
        if input_type == self:
            return input
        # We don't support implicit conversion
        if implicit:
            return None
        # We support anything that can convert to a number
        input_as_num = adapt(input, Unsigned(length=input_type.get_num_bits()), implicit, force)
        if input_as_num is None:
            return None
        return Struct.FromNumber(self)(input_as_num)

class Interface(Composite):
    def __init__(self):
        super().__init__(support_reverse = True)
    def get_unconnected_value(self, back_end: 'BackEnd') -> str:
        raise SyntaxErrorException(f"Unconnected interfaces are not supported")
    def get_default_value(self, back_end: 'BackEnd') -> str:
        raise SyntaxErrorException(f"Unconnected interfaces are not supported")



class Array(Composite):
    def __init__(self, member_type: NetType, size: int):
        super().__init__(support_reverse = False)

        self.size = size
        self.member_type = member_type
        if member_type.is_abstract():
            raise SyntaxErrorException(f"Array doesn't support abstract members")
        for idx in range(self.size):
            super().add_member(f"element_{idx}", member_type)

    def add_member(self, name: str, member: Union[NetType, Reverse]) -> None:
        raise SyntaxErrorException(f"Arrays don't support dynamic members")

    class Accessor(GenericModule):
        @staticmethod
        def create_output_type(key: Number.Key, array: 'Array') -> 'Array':
            if key.length == 1:
                # This is a member access
                return array.member_type
            else:
                # This is an array slice
                return array(array.member_type, key.length)

        """
        Accessor instances are used to implement the following constructs:

        b <<= a[3]
        b <<= a[3:0]
        b <<= a[3:0][2]

        They are instantiated from Array.get_slice, which is called from Junction.__getitem__ and from MemberGetter.get_underlying_junction
        """
        def construct(self, slice: Union[int, slice], array: 'Array') -> None:
            self.key = Number.Key(slice)
            self.input_port = Input(array)
            self.output_port = Output(self.create_output_type(self.key, array))

        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))
        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"
            input_type = self.input_port.get_net_type()

            start = self.key.start
            end = self.key.end
            if start < 0 or end >= input_type.size:
                raise SyntaxErrorException("Slice bounds are outside of Array size")
            ret_val = ""
            if end != start:
                op_precedence = back_end.get_operator_precedence("{}")
                ret_val += "{"
            else:
                op_precedence = 0 # I think ??
            members = self.input_port.get_all_member_junctions(add_self=False)
            first = True
            for idx, (member) in reversed(tuple(enumerate(members))):
                if idx >= start and idx <= end:
                    name, _ = member.get_rhs_expression(back_end, target_namespace)
                    if not first:
                        ret_val += ", "
                        first = False
                    ret_val += f"{name}"
            if end != start:
                ret_val += "}"
            return ret_val, op_precedence

        @staticmethod
        def static_sim(in_junction: Junction, key: 'Number.Key'):
            output_type = Array.Accessor.create_output_type(key, in_junction.get_net_type())
            members = in_junction.get_all_member_junctions(add_self=False)
            important_members = []
            for idx, (member) in reversed(enumerate(members)):
                if idx >= key.start and idx <= key.end:
                    important_members.append(member)
            return output_type(*important_members)

        def simulate(self) -> TSimEvent:
            output_type = Array.Accessor.create_output_type(self.key, self.input_port.get_net_type())
            members = self.input_port.get_all_member_junctions(add_self=False)
            important_members = []
            for idx, (member) in reversed(enumerate(members)):
                if idx >= self.key.start and idx <= self.key.end:
                    important_members.append(member)
            while True:
                yield important_members
                self.output_port <<= output_type(*important_members)

        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            assert False
        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

    def get_slice(self, key: Any, junction: Junction) -> Any:
        if junction.active_context() == "simulation":
            return Array.Accessor.static_sim(junction, Number.Key(key))
        else:
            return Number.Accessor(slice=key, array=self)(junction)

    def set_member_access(self, key: Any, value: Any, junction: Junction) -> None:
        # The junction conversion *has* to happen before the creation of the Concatenator.
        # Otherwise, the auto-created converter object (such as Constant) will be evaluated in the wrong order
        # and during the evaluation of the Concatenator, the inlined expression forwarding logic will break.
        from .utils import convert_to_junction
        real_junction = convert_to_junction(value)
        junction.raw_input_map.append((key, real_junction))
    @classmethod
    def resolve_key_sequence_for_get(cls, keys: Sequence[Tuple[Any, KeyKind]], for_junction: Junction) -> Tuple[Optional[Sequence[Tuple[Any, KeyKind]]], Junction]:
        # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing
        # Returns the final junction and the remaining keys if they cannot be processed.
        # NOTE: for Numbers, this is easy, as the chain always produces more Numbers,
        #       so we should be able to fully process the chain. For other types, such
        #       as structs or interfaces, things get more complicated.
        # NOTE: Again, for Numbers only, set and get variants are nearly identical.
        remaining_keys, key = cls.resolve_key_sequence_for_set(keys)
        if len(remaining_keys) == 0:
            remaining_keys = None
        return remaining_keys, Array.Accessor(slice=key, array=for_junction.get_net_type())(for_junction)
    @classmethod
    def resolve_key_sequence_for_set(cls, keys: Sequence[Tuple[Any, KeyKind]]) -> Any:
        # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing for concatenators (set context)
        # Returns remaining keys (if any) and the resolved slice

        def _slice_of_slice(outer_key: Any, inner_key: Any) -> Any:
            # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing
            outer_key = Number.Key(outer_key)
            inner_key = Number.Key(inner_key)
            result_key = outer_key.apply(inner_key)
            if result_key.start == result_key.end:
                return result_key.start
            else:
                return slice(result_key.start, result_key.end, -1)

        def key_length(key):
            if isinstance(key, int):
                return 1
            return key.end - key.start + 1

        key = keys[0]
        assert key[1] is KeyKind.Index, "Array doesn't support member access, only slices"
        key = key[0]
        idx = 0
        if key_length(key) > 1:
            for idx, sub_key in enumerate(keys[1:]):
                assert sub_key[1] is KeyKind.Index, "Array doesn't support member access, only slices"
                key = _slice_of_slice(key, sub_key[0])
                if key.length < 1:
                    SyntaxErrorException("Invalid slicing of array: at least one member must be selected.")
                if key_length(key) == 1:
                    break
        return keys[1:][idx:-1], key



# DUST-BIN: these objects aren't used at the momemnt, but might be in the future...
    '''
    class Key(object):
        def __init__(self, thing: Any):
            self.key = str(thing)

    class Key(object):
        def __init__(self, thing: Any):
            self.key = str(thing)
        def __eq__(self, other) -> bool:
            return self.key == other.key
        def __ne__(self, other) -> bool:
            return self.key != other.key
        def __hash__(self) -> str:
            return self.key.__hash__()

    class InterfaceAccessor(GenericModule):
        input_port = Input()
        output_port = Output()

        def construct(self, for_type: 'Interface', member: str) -> None:
            if member not in for_type.get_members():
                raise SyntaxErrorException(f"Interface {for_type} doesn't have a member named {member}")
            self.member = member

        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            assert len(self.get_outputs()) == 1
            yield (self.output_port, *self.generate_inline_expression(back_end, target_namespace), InlineKind.expression)

        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"
            op_precedence = back_end.get_operator_precendence(".")
            input_expression, _ = self.input_port.get_rhs_expression(back_end, target_namespace, None, op_precedence)
            return f"{input_expression}.{self.member}", op_precedence


        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            assert False

        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

        def simulate(self) -> TSimEvent:
            while True:
                yield self.get_inputs().values()
                self.output_port <<= getattr(self.input_port.sim_value, self.member)

    class StructCombiner(GenericModule):
        def construct(self, output_net_type: 'Struct') -> None:
            from .port import Input, Output
            self.output_port = Output(output_net_type)
            self.output_port.set_parent_module(self)
            members = output_net_type.members
            self.member_names = tuple(member[0] for member in members)
            for (member_name, member_type) in members:
                port = Input(member_type)
                port.set_parent_module(self)
                setattr(self, member_name, port)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end)
            ret_val += "\nassign output_port = '{"
            last_key = len(self.member_names)-1
            for idx, member_name in enumerate(self.member_names):
                ret_val += "{}: {}".format(member_name, member_name)
                if idx != last_key:
                    ret_val += ", "
            ret_val += "}\n"
            ret_val += "endmodule\n\n\n"
            return ret_val
    '''