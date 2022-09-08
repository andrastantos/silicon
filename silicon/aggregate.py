from typing import Tuple, Union, Any, Dict, Set, Optional, Generator, Sequence

from .net_type import NetType, KeyKind, NetTypeFactory, NetTypeMeta, suppress_init
from .netlist import Netlist
from .back_end import BackEnd
from .exceptions import SimulationException, SyntaxErrorException
from .module import Module, GenericModule, InlineExpression, InlineBlock, InlineStatement
from .port import Input, Output, Junction
from .utils import TSimEvent, adapt, Context, is_net_type
from collections import OrderedDict
from .number import Unsigned, Number
from .port import Wire
from .exceptions import AdaptTypeError, InvalidPortError
from .composite import Reverse, is_reverse, is_composite_member
import types

class Aggregate(NetType):
    """
    A Composite type is the base for both interfaces and structs
    """

    def __init_subclass__(cls, support_reverse: bool):
        cls._support_reverse = support_reverse
        cls._init_members()

    class MemberDesc(object):
        def __init__(self, member: NetType, is_reversed: bool):
            self.member = member
            self.is_reversed = is_reversed
 
    @classmethod
    def _init_members(cls):
        cls.members: Dict[str, 'Aggregate.MemberDesc'] = OrderedDict()
        for name in dir(cls):
            # Skip all dunder attributes
            # The reason for it is that the type system is recursive. That is to say, that __base__ and such
            # might contain things that are NetTypes, thus would qualify as a composite member.
            if name.startswith("__") and name.endswith("__"):
                continue
            try:
                val = getattr(cls,name)
            except AttributeError:
                continue
            if is_composite_member(val):
                cls.add_member(name, val)

    @classmethod
    def add_member(cls, name: str, member: Union[type, Reverse]) -> None:
        if not hasattr(cls, "members"):
            raise SyntaxErrorException("Can only add members to a Composite-derived type")
        if name in cls.members:
            raise SyntaxErrorException(f"Member {name} already exists on composite type {cls}")
        if is_net_type(member):
            cls.members[name] = Aggregate.MemberDesc(member, False)
        elif is_reverse(member):
            if cls._support_reverse:
                cls.members[name] = Aggregate.MemberDesc(member.net_type, True)
            else:
                raise SyntaxErrorException(f"Composite type {cls} doesn't support reverse members")
        else:
            raise SyntaxErrorException(f"Composite type members must be either NetTypes or Reverse(NetType)-s. {member} is of type {type(member)}")

    @classmethod
    def get_members(cls) -> Dict[str, 'Aggregate.MemberDesc']:
        return cls.members

    @classmethod
    def generate_type_ref(cls, back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return str(cls.__name__)

    @classmethod
    def generate_net_type_ref(cls, for_port: 'Junction', back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return f"{cls.generate_type_ref(back_end)}.{for_port.generate_junction_ref(back_end)}_port"

    @classmethod
    def get_num_bits(cls) -> int:
        return sum(member.member.get_num_bits() for member in cls.get_members().values())

    @classmethod
    @property
    def vcd_type(cls) -> str:
        return None

    @classmethod
    def _generate_member_names(cls, prefix: str, back_end: 'BackEnd') -> Sequence[str]:
        member_names = []
        for name, member_desc in cls.get_members().items():
            member_name = prefix + back_end.get_member_delimiter() + name
            if hasattr(member_desc.member, "_generate_member_names"):
                member_names += member_desc.member._generate_member_names(member_name)
            else:
                member_names.append(member_name)
        return member_names

    @classmethod
    def generate_assign(cls, sink_name: str, source_expression: str, xnet: 'XNet', back_end: 'BackEnd') -> str:
        member_names = cls._generate_member_names(sink_name, back_end)
        # TODO: beautify this expression with new lines and indentation
        return f"assign {', '.join(member_names)} = {source_expression};"

    @classmethod
    def get_unconnected_sim_value(cls) -> Any:
        return None

    @classmethod
    def get_default_sim_value(cls) -> Any:
        return None

    def __new__(cls, *args, **kwargs):
        # If an instance is ever created for this type, we'll have to disable add_member.
        # The reason is this: we rely on type-equivalence to determine compatibility. That
        # requires that all instances of an Aggregate have the same members. Which in turn
        # requires that members are class variables. So, add_member really adds a member
        # to *all existing instances* of an Aggregate. That is almost certainly *not* what
        # was intended if add_member was called on an instance. So what we'll do is to 
        # hide the class-level method by providing an instance-level one with the same name
        # that just raises an exception
        ret_val = super().__new__(cls, *args, **kwargs)
        ret_val.add_member = ret_val._add_member_override
        return ret_val

    def _add_member_override(self, name: str, member: Union[NetType, Reverse]) -> None:
        raise SyntaxErrorException(f"Arrays don't support dynamic members")

    class RhsSlice(GenericModule):
        """
        Accessor instances are used to implement the following constructs:

        b <<= a[3]
        b <<= a[3:0]
        b <<= a[3:0][2]

        They are instantiated from Aggregate.get_slice and Aggregate.get_rhs_slicer.

        TODO: get_slice will need review
        """
        def construct(self, member_name: str, aggregate: 'Aggregate') -> None:
            self.key = member_name
            if member_name not in aggregate.get_members():
                raise SyntaxErrorException(f"Aggregate '{aggregate}' doesn't have a member named '{member_name}'")
            member_type = aggregate.get_members()[member_name]
            self.input_port = Input(member_type)
            self.output_port = Output(aggregate)
        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))
        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"

            # Since we blow up aggregates into individual wires in RTL, we'll need to get a name for the rhs, not an expression
            rhs_name, precedence = self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), allow_expression = False)
            rhs_name = rhs_name + back_end.get_member_delimiter() + self.key
            return rhs_name, precedence

        @staticmethod
        def static_sim(in_val: Any, key: str):
            assert False

        def simulate(self) -> TSimEvent:
            while True:
                yield self.input_port
                in_val = self.input_port.sim_value
                if in_val is None:
                    out_val = None
                else:
                    out_val = in_val.get_member(self.member_name)
                self.output_port <<= out_val

        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            assert False

        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

    def get_rhs_slicer(self, key: Any, key_kind: KeyKind) -> 'Module':
        if key_kind != KeyKind.Index:
            raise SyntaxErrorException("FIXME: Aggregates should support attribute-access as well as array-style member access.")
        return Aggregate.RhsSlice(key, self.get_net_type())

    class PhiSlice(GenericModule):
        """
        This class handles the case of member-wise assignment to Aggregates. Things, like:

        a[3:0] <<= b
        a[3:0][1] <<= c

        and things like that.

        PhiSlices are type-specific and have different guts for ex. Numbers.

        For Aggregates, they are collecting *all* the assignments to a given junction and generate
        a single assignment Verilog statement. This is needed because Silicon treats Aggregates as a single
        entity and expects to be able to generate a single assignment.
        """
        output_port = Output()

        def construct(self, key_chains: Sequence[Sequence[Tuple[Any, KeyKind]]], aggregate: 'Aggregate'):
            self.key_chains = key_chains
            self.input_map = None
            self.output_port.set_net_type(aggregate)

        def create_positional_port_callback(self, idx: int, net_type: Optional['NetType'] = None) -> Tuple[str, Port]:
            # Create the associated input to the key. We don't support named ports, only positional ones.
            if idx >= len(self.key_chains):
                raise InvalidPortError
            name = f"slice_{idx}"
            ret_val = Input(net_type)
            return name, ret_val

        def create_named_port_callback(self, name: str, net_type: Optional['NetType'] = None) -> Optional[Port]:
            raise InvalidPortError()

        def finalize_input_map(self, common_net_type: object):
            if self.input_map is not None:
                return
            self.input_map = OrderedDict()
            keyed_inputs = set()
            for raw_key, input in zip(self.key_chains, self.get_inputs().values()):
                remaining_keys, final_key = common_net_type.resolve_key_sequence_for_set(raw_key)
                if remaining_keys is not None:
                    raise FixmeException("Can't resolve all keys in a LHS context. THIS COULD BE FIXED!!!!")
                key = common_net_type.Key(final_key) # Convert the raw key into something that the common type understands
                if key in self.input_map:
                    raise SyntaxErrorException(f"Input key {raw_key} is not unique for concatenator output type {common_net_type}")
                self.input_map[key] = input
                keyed_inputs.add(input)
            for input in self.get_inputs().values():
                assert input in keyed_inputs, f"Strange: PhiSlice has an input {input} without an associated key"

        def body(self) -> None:
            pass

        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))
        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            return self.output_port.get_net_type().compose_concatenated_expression(back_end, self.input_map, target_namespace)
        def simulate(self) -> TSimEvent:
            net_type = self.output_port.get_net_type()
            cache = net_type.prep_simulate_concatenated_expression(self.input_map)
            while True:
                yield self.get_inputs().values()
                self.output_port <<= net_type.simulate_concatenated_expression(cache)

        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

    @staticmethod
    def get_lhs_slicer(key_chains: Sequence[Sequence[Tuple[Any, KeyKind]]]) -> 'Module':
        return Number.PhiSlice(key_chains)
        
    @classmethod
    def resolve_key_sequence_for_get(cls, keys: Sequence[Tuple[Any, KeyKind]], for_junction: Junction) -> Tuple[Optional[Sequence[Tuple[Any, KeyKind]]], Junction]:
        # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing
        # Returns the final junction and the remaining keys if they cannot be processed.
        # NOTE: for Aggregates, this is easy, as the chain can only have a single element.
        remaining_keys, key = cls.resolve_key_sequence_for_set(keys)
        member_name = key[0]
        if member_name not in cls.members:
            raise SyntaxErrorException(f"'{member_name}' is not a member of '{cls}'")
        member_desc = cls.members[member_name]
        return remaining_keys, Aggregate.RhsSlice(member_name, member_desc.member)(for_junction)

    @classmethod
    def resolve_key_sequence_for_set(cls, keys: Sequence[Tuple[Any, KeyKind]]) -> Any:
        # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing for PhiSlices (set context)
        # Returns remaining keys and the resolved slice
        # For aggregates, this is trivial: they key sequence is always a single entry
        return keys[1:], keys[0]

















def is_struct(thing: Any) -> bool:
    try:
        return issubclass(thing, Struct)
    except TypeError:
        return False

class Struct(Composite, support_reverse=False):
    def __init_subclass__(cls):
        cls._init_members()

    def __new__(cls, *args, **kwargs) -> Union['Struct', 'Junction']:
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

        We should also support:

            my_wire = Input(RGB)

        This will end up calling RGB() (eventually, when the type becomes part of the inheritance hierarchy), because the above is equivalent to:

            my_wire = RGB_Input()

        In this case we should simply return a Struct instance.
        """
        if len(args) == 0 and len(kwargs) == 0:
            # This is the port creation case
            return super().__new__(cls)
        if len(args) == 1 and len(kwargs) == 0:
            # This is te explicit type-conversion path
            return super().__new__(cls, *args)
        # We're in the element-wise assignment regime
        args_idx = 0
        assigned_names = set()
        # First assign positional arguments, only after exhausting that list, start looking at named ones
        members = cls.get_members()
        output_junction = Wire(cls)
        for member_name, (member, reversed) in members.items():
            if args_idx < len(args):
                if (reversed):
                    raise SyntaxErrorException("Can't assign to reversed members of a Composite type")
                member = getattr(output_junction, member_name)
                member <<= args[args_idx]
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
            member = getattr(output_junction, member_name)
            member <<= value
            assigned_names.add(member_name)
        return suppress_init(output_junction)

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
            if not is_struct(net_type) and net_type is not None:
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
                if first_type is not net_type:
                    raise SyntaxErrorException("SELECT is only supported on structs of the same type")
            return first_type
        else:
            return super().result_type(net_types, operation) # Will raise an exception.

    @classmethod
    def get_lhs_name(cls, for_junction: Junction, back_end: BackEnd, target_namespace: Module, allow_implicit: bool=True) -> Optional[str]:
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

    @classmethod
    def adapt_to(cls, output_type: 'NetType', input: 'Junction', implicit: bool, force: bool) -> Optional['Junction']:
        assert input.get_net_type() is cls
        if output_type is cls:
            return input
        # We don't support implicit conversion
        if implicit:
            raise AdaptTypeError
        # We only support conversion to Numbers
        raw_number = Struct.ToNumber(input.get_net_type())(input)
        if raw_number.get_net_type() is output_type:
            return raw_number
        return adapt(raw_number, output_type, implicit, force)

    @classmethod
    def adapt_from(cls, input: Any, implicit: bool, force: bool) -> Any:
        context = Context.current()
        if context == Context.simulation:
            raise SimulationException("Don't support simulation yet")
        elif context == Context.elaboration:
            input_type = input.get_net_type()
            if input_type is cls:
                return input
            # We don't support implicit conversion
            if implicit:
                raise AdaptTypeError
            # We support anything that can convert to a number
            input_as_num = adapt(input, Unsigned(length=input_type.get_num_bits()), implicit, force)
            if input_as_num is None:
                raise AdaptTypeError
            return Struct.FromNumber(cls)(input_as_num)
        else:
            assert False, f"Unknown context: {context}"
class Interface(Composite, support_reverse=True):
    def __init_subclass__(cls):
        cls._init_members()

    @classmethod
    def get_unconnected_value(cls, back_end: 'BackEnd') -> str:
        raise SyntaxErrorException(f"Unconnected interfaces are not supported")
    @classmethod
    def get_default_value(cls, back_end: 'BackEnd') -> str:
        raise SyntaxErrorException(f"Unconnected interfaces are not supported")


class _ArrayType(Composite, support_reverse=False):
    Key = Number.Instance.Key

    def __init_subclass__(cls):
        cls._init_members()

    @classmethod
    def _add_member_override(cls, name: str, member: Union[NetType, Reverse]) -> None:
        raise SyntaxErrorException(f"Arrays don't support dynamic members")
    @classmethod
    def _init_members_override(cls):
        pass


    class Accessor(GenericModule):
        @staticmethod
        def create_output_type(key: '_ArrayType.Key', array: '_ArrayType') -> '_ArrayType':
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

        They are instantiated from _ArrayType.get_slice, which is called from Junction.__getitem__ and from MemberGetter.get_underlying_junction
        """
        def construct(self, slice: Union[int, slice], array: '_ArrayType') -> None:
            self.key = _ArrayType.Key(slice)
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
        def static_sim(in_junction: Junction, key: '_ArrayType.Key'):
            output_type = _ArrayType.Accessor.create_output_type(key, in_junction.get_net_type())
            members = in_junction.get_all_member_junctions(add_self=False)
            important_members = []
            for idx, (member) in reversed(enumerate(members)):
                if idx >= key.start and idx <= key.end:
                    important_members.append(member)
            return output_type(*important_members)

        def simulate(self) -> TSimEvent:
            output_type = _ArrayType.Accessor.create_output_type(self.key, self.input_port.get_net_type())
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

    @classmethod
    def get_slice(cls, key: Any, junction: Junction) -> Any:
        if Context.current() == Context.simulation:
            return _ArrayType.Accessor.static_sim(junction, _ArrayType.Key(key))
        else:
            return Number.Accessor(slice=key, array=cls)(junction)

    @classmethod
    def set_member_access(cls, key: Any, value: Any, junction: Junction) -> None:
        # The junction conversion *has* to happen before the creation of the Concatenator.
        # Otherwise, the auto-created converter object (such as Constant) will be evaluated in the wrong order
        # and during the evaluation of the Concatenator, the inlined expression forwarding logic will break.
        from .utils import convert_to_junction
        real_junction = convert_to_junction(value, type_hint=None)
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
        return remaining_keys, _ArrayType.Accessor(slice=key, array=for_junction.get_net_type())(for_junction)
    @classmethod
    def resolve_key_sequence_for_set(cls, keys: Sequence[Tuple[Any, KeyKind]]) -> Any:
        # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing for concatenators (set context)
        # Returns remaining keys (if any) and the resolved slice

        def _slice_of_slice(outer_key: Any, inner_key: Any) -> Any:
            # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing
            outer_key = _ArrayType.Key(outer_key)
            inner_key = _ArrayType.Key(inner_key)
            result_key = outer_key.apply(inner_key)
            if result_key.start == result_key.end:
                return result_key.start
            else:
                return slice(result_key.start, result_key.end, -1)

        def key_length(key):
            try:
                _ = int(key)
                return 1
            except TypeError:
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


class Array(NetTypeFactory, net_type=_ArrayType):
    instances = {}

    @classmethod
    def construct(cls, net_type, member_type: NetTypeMeta, size: int):
        try:
            size = int(size)
        except TypeError:
            raise SyntaxErrorException("Array size must be an integer")

        # NOTE: the name of the type could be anything really, doesn't have to be something that's a valid identifier.
        #       This could be important, because we can avoid name-collisions this way.
        type_name = f"Array_{member_type.__name__}[{size}]"
        key = (member_type, size)
        if net_type is not None:
            net_type.member_type = member_type
            net_type.size = size
            for idx in range(size):
                net_type.add_member(f"element_{idx}", member_type)
            # Disabling further adding of members, even when the Array is further sub-classed
            net_type.add_member = net_type._add_member_override
            net_type._init_members = net_type._init_members_override
        return type_name, key


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