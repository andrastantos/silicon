from typing import Optional, Any, Tuple, Generator, Union, Dict, Set, Sequence
from .exceptions import SyntaxErrorException, SimulationException
from .net_type import NetType, KeyKind, behavior
from .module import GenericModule, Module, InlineBlock, InlineExpression, has_port
from .port import Input, Output, Junction, Port
from .tracer import no_trace
from .utils import first, TSimEvent, get_common_net_type, is_subscriptable
from collections import OrderedDict

class Number(NetType):
    """
    Number is a range-tracking bit-vector, the basic type of Silicon.

    It has a minimum and a maximum value, from which the number of bits
    required for representing that range can be derived.

    If the range contains negative numbers, the representation is 2's complement.
    If the range is non-negative, an unsigned representation is used.

    NOTE: range is inclusive because Pythons 'range' concept (stop is not in the range, but start is) is
    just too obnoxious to use
    """

    # The associated VCD type (one of VAR_TYPES inside vcd.writer.py)
    vcd_type: str = 'wire'

    def __init__(self, length: Optional[int] = None, signed: Optional[bool] = None, min_val: Optional[int] = None, max_val: Optional[int] = None):
        self.min_val = min_val
        self.max_val = max_val
        self.signed = signed
        self.length = length
        self._calc_metrics()

    def __str__(self) -> str:
        signed_str = 's' if self.signed else 'u'
        return f"Number({signed_str}{self.length} {self.min_val}...{self.max_val})"

    def __repr__(self) -> str:
        signed_str = 's' if self.signed else 'u'
        return f"Number({signed_str}{self.length} {self.min_val}...{self.max_val})"

    def __eq__(self, other):
        if not isinstance(other, Number):
            return False
        return self is other or (self.min_val == other.min_val and self.max_val == other.max_val and self.length == other.length and self.signed == other.signed)
    
    def __hash__(self):
        return hash(self.min_val, self.max_val)

    class Key(object):
        def __init__(self, thing: Union[int, slice, None] = None):
            if isinstance(thing, slice):
                self.start = thing.start
                self.end = thing.stop
                if thing.step is not None and thing.step != 1 and thing.step != -1:
                    raise SyntaxErrorException("Number slices must be contiguous")
                if self.end > self.start:
                    raise SyntaxErrorException("Number slices must be from high- to low-order bits")
                self.is_sequential = False
            elif isinstance(thing, int):
                self.start = thing
                self.end = thing
                self.is_sequential = False
            elif thing is None:
                # We need to create a sequential key
                self.is_sequential = True
            else:
                raise SyntaxErrorException("Number slices must be integers or integer ranges.")
        @property
        def length(self) -> int:
            return self.start - self.end + 1
        def apply(self, inner_key: 'Number.Key') -> 'Number.Key':
            result = Number.Key(0) # Just to have it initialized. We'll override members below...
            result.end = self.end + inner_key.end
            result.start = self.end + inner_key.start
            if result.end > self.start or result.start > self.start:
                raise SyntaxErrorException("Slice of slices is out of bounds. The inner slice cannot fit in the outer one")
            return result

    class Accessor(GenericModule):
        def construct(self, slice: Union[int, slice], number: 'Number') -> None:
            self.key = Number.Key(slice)
            self.input = Input(number)
            # At least in SystemVerilog slice always returns unsigned.
            # That I think makes more sense so I'll implement it that way here too.
            # This of course means that signed_number[3:0] for a 4-bit signed is not a no-op!
            # This is listed as a gottcha here: https://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.449.1578&rep=rep1&type=pdf
            #self.output = Output(Number(length=self.key.length, signed=number.signed))
            self.output = Output(Number(length=self.key.length, signed=False))
        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            yield InlineExpression(self.output, *self.generate_inline_expression(back_end, target_namespace))
        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"

            op_precedence = back_end.get_operator_precedence("[]")
            rhs_name, _ = self.input.get_rhs_expression(back_end, target_namespace, self.output.get_net_type(), op_precedence)
            assert self.key.start <= self.input.get_net_type().length, "FIXME: accessing slices of a Number outside it's length is not yet supported!!"
            if self.key.end == self.key.start:
                return f"{rhs_name}[{self.key.start}]", op_precedence
            else:
                return f"{rhs_name}[{self.key.start}:{self.key.end}]", op_precedence

        @staticmethod
        def static_sim(in_val: int, key: 'Number.Key'):
            shift = key.end
            mask = (1 << (key.start - key.end + 1)) - 1
            if in_val is None:
                out_val = None
            else:
                out_val = (in_val >> shift) & mask
            return out_val

        def simulate(self) -> TSimEvent:
            shift = self.key.end
            mask = (1 << (self.key.start - self.key.end + 1)) - 1
            while True:
                yield self.input
                in_val = self.input.sim_value
                if in_val is None:
                    out_val = None
                else:
                    out_val = (in_val >> shift) & mask
                self.output <<= out_val
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            assert False
        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

    def get_lhs_name(self, for_junction: Junction, back_end: 'BackEnd', target_namespace: Module, allow_implicit: bool=True) -> Optional[str]:
        assert back_end.language == "SystemVerilog"
        xnet = target_namespace._impl.netlist.get_xnet_for_junction(for_junction)
        name = xnet.get_lhs_name(target_namespace, allow_implicit=allow_implicit)
        if name is None:
            return None
        return name

    def get_rhs_expression(self, for_junction: Junction, back_end: 'BackEnd', target_namespace: Module, outer_precedence: Optional[int] = None) -> Tuple[str, int]:
        xnet = target_namespace._impl.netlist.get_xnet_for_junction(for_junction)
        expr, prec = xnet.get_rhs_expression(target_namespace, back_end)
        if outer_precedence is not None and prec > outer_precedence:
            return f"({expr})", back_end.get_operator_precedence("()")
        else:
            return expr, prec

    def generate_type_ref(self, back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        assert not self.is_abstract(), "Can't generate RTL for abstract Numbers"
        if self.signed:
            if self.length > 1:
                return f"logic signed [{self.length - 1}:0]"
            else:
                return f"logic signed"
        else:
            if self.length > 1:
                return f"logic [{self.length - 1}:0]"
            else:
                return f"logic"

    def generate_net_type_ref(self, for_junction: 'Junction', back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return f"{for_junction.generate_junction_ref(back_end)} {self.generate_type_ref(back_end)}"

    class MemberSetter(Module):
        output_port = Output()

        def construct(self):
            self.raw_input_map = []
            self.input_map = None
        def add_input(self, key: 'Key', junction: Junction) -> None:
            name = f"input_port_{len(self.raw_input_map)}"
            if has_port(self, name):
                raise SyntaxErrorException(f"Can't add input to {self} as port name {name} already exists")
            port = self._impl._create_named_port(name)
            port <<= junction
            self.raw_input_map.append((key,  getattr(self, name)))
        def create_named_port(self, name: str) -> Optional[Port]:
            if name.startswith("input_port_"):
                return Input()
            else:
                return None
        def create_positional_port(self, idx: int) -> Optional[Union[str, Port]]:
            return None

        def finalize_input_map(self, common_net_type: object):
            if self.input_map is not None:
                return
            self.input_map = OrderedDict()
            keyed_inputs = set()
            for (raw_key, input) in self.raw_input_map:
                final_key = common_net_type.resolve_key_sequence_for_set(raw_key)
                key = common_net_type.Key(final_key) # Convert the raw key into something that the common type understands
                if key in self.input_map:
                    raise SyntaxErrorException(f"Input key {raw_key} is not unique for concatenator output type {common_net_type}")
                self.input_map[key] = input
                keyed_inputs.add(input)
            for input in self.get_inputs().values():
                assert input in keyed_inputs, f"Strange: MemberSetter has an input {input} without an asscoated key"

        def generate_output_type(self) -> Optional['Number']:
            # This is one of the few cases where we do care about what port we're driving.
            # The reason for that is partial assignments, that are not allowed.
            # Let's say we have something, like this:
            #     w = Wire(Unsigned(8))
            #     w[0] = 1
            # This piece of code should not elaborate. However, if MemberSetter
            # auto-determines its output type, it'll think it's a 1-bit output.
            # Then auto-type-conversion simply zero-extends that to the rest of the bits.
            # To make things even more confusing for the user, this is an error:
            #     w = Wire(Unsigned(8))
            #     w[1] = 1
            # So, to remedy that, we'll look at the transitive closure of all sinks
            # of our output and use the smallest output range from them.
            # Why the smallest? Because if there are multiple sources,
            # those should participate in auto-extension. If it so happens
            # that our direct output is not the most restritive, that would
            # mean that somewhere in the assignment chain, there was a narrowing,
            # which will eventually blow up.
            from .number import Number
            common_net_type = get_common_net_type(self.get_inputs().values())
            if common_net_type is None:
                raise SyntaxErrorException(f"Can't figure out output port type for MemberSetter {self}")
            if not common_net_type is Number:
                raise SyntaxErrorException(f"MemberSetter resulte type is {common_net_type}. It should be a Number")
            self.finalize_input_map(common_net_type)
            sinks = self.output_port.get_all_sinks()
            min_val = None
            max_val = None
            for sink in sinks:
                if not sink.is_abstract() and isinstance(sink.get_net_type(), Number):
                    if min_val == None:
                        min_val = sink.get_net_type().min_val
                    else:
                        min_val = max(min_val, sink.get_net_type().min_val)
                    if max_val == None:
                        max_val = sink.get_net_type().max_val
                    else:
                        max_val = min(max_val, sink.get_net_type().max_val)
            if min_val is not None:
                assert max_val is not None
                output_type = Number(min_val=min_val, max_val=max_val)
            else:
                output_type = common_net_type.concatenated_type(self.input_map)
            return output_type

        
        def body(self) -> None:
            new_net_type = self.generate_output_type()
            if new_net_type is None:
                raise SyntaxErrorException(f"Can't figure out output port type for MemberSetter {self}")
            assert not self.output_port.is_specialized()
            self.output_port.set_net_type(new_net_type)

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


    class Iterator(object):
        def __init__(self, net_type: 'Number', junction: Junction):
            self.parent_junction = junction
            self.idx = 0
            self.length = net_type.get_length()
        def __next__(self):
            if self.idx == self.length:
                raise StopIteration
            ret_val = self.parent_junction[self.idx]
            self.idx += 1
            return ret_val
    def get_iterator(self, parent_junction: Junction) -> Any:
        """
        Returns an iterator for the type (such as one that iterates through all the bits of a number)
        """
        return Number.Iterator(self, parent_junction)
    def get_length(self) -> int:
        return self.length
    
    def get_slice(self, key: Any, junction: Junction) -> Any:
        if junction.active_context() == "simulation":
            return Number.Accessor.static_sim(junction.sim_value, Number.Key(key))
        else:
            return Number.Accessor(slice=key, number=self)(junction)
    
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
        key = cls.resolve_key_sequence_for_set(keys)
        return None, Number.Accessor(slice=key, number=for_junction.get_net_type())(for_junction)
    @classmethod
    def resolve_key_sequence_for_set(cls, keys: Sequence[Tuple[Any, KeyKind]]) -> Any:

        def _slice_of_slice(outer_key: Any, inner_key: Any) -> Any:
            # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing
            outer_key = Number.Key(outer_key)
            inner_key = Number.Key(inner_key)
            result_key = outer_key.apply(inner_key)
            if result_key.start == result_key.end:
                return result_key.start
            else:
                return slice(result_key.start, result_key.end, -1)

        # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing for concatenators (set context)
        # Returns the resolved slice
        key = keys[0]
        assert key[1] is KeyKind.Index, "Number doesn't support member access, only slices"
        key = key[0]
        for sub_key in keys[1:]:
            assert sub_key[1] is KeyKind.Index, "Number doesn't support member access, only slices"
            key = _slice_of_slice(key, sub_key[0])
        return key
    def is_abstract(self) -> bool:
        return self.length is None and self.min_val is None and self.max_val is None

    def _calc_metrics(self):
        if self.is_abstract():
            if self.signed is None:
                raise SyntaxErrorException("Abstract Number types must have signage specified")
            return
        if self.length is None:
            if self.min_val is None or self.max_val is None:
                raise SyntaxErrorException("Number objects must have either their range or their length specified")
            if self.min_val > self.max_val:
                raise SyntaxErrorException("The min_val value of a Number object must not be greater than max_val")
            if self.min_val < 0: # In theory, we only need the sign bit if min and max straddle 0, but that would leave us with an unsigned representation for negative ranges.
                self.length = max(abs(self.max_val), abs(self.min_val + 1)).bit_length() + 1
                self.signed = True
            else:
                self.length = self.max_val.bit_length()
                # (0).bit_length() is 0, so let's patch that up
                if self.length == 0:
                    self.length = 1
                self.signed = False
        else:
            if self.signed is None:
                raise SyntaxErrorException("For Number objects if length is specified, signed must be specified as well")
            if self.signed:
                len_max_val = 2 ** (self.length - 1) - 1
                len_min_val = -(2 ** (self.length - 1))
            else:
                len_max_val = 2 ** self.length - 1
                len_min_val = 0
            if self.max_val is None:
                self.max_val = len_max_val
            if self.min_val is None:
                self.min_val = len_min_val
            if self.min_val < len_min_val:
                raise SyntaxErrorException("Length and min_val are both specified, but are incompatible")
            if self.max_val > len_max_val:
                raise SyntaxErrorException("Length and max_val are both specified, but are incompatible")

    def get_unconnected_sim_value(self) -> Any:
        return None
    def get_default_sim_value(self) -> Any:
        return 0
    def validate_sim_value(self, sim_value: Any, parent_junction: Junction) -> Any:
        """
        Validates the new sim value before assignment.

        Raises exceptions with appropriate error messages in case of a validation error.
        
        Has the option to change/correct the sim_value prior to assignment.
        
        Returns potentially modified sim_value for assignment.
        """
        if sim_value is None:
            return sim_value
        if sim_value > self.max_val or sim_value < self.min_val:
            raise SimulationException(f"Can't assign to net {parent_junction} a value {sim_value} that's outside of the representable range.")
        return sim_value

    def generate_const_val(self, value: Optional[int], back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        length = self.length
        if value is None:
            return f"{length}'bX"
        if value >= 0:
            return f"{length}'h{format(value, 'x')}"
        else:
            return f"-{length}'sh{format(-value, 'x')}"

    def get_num_bits(self) -> int:
        return self.length

    def convert_to_vcd_type(self, value: Optional[int]) -> Any:
        """
        Converts the given native python value into the corresponding VCD-compatible value
        Must be overwritten for all sub-classes
        """
        if value is None:
            return 'X'
        return value

    def get_junction_member(self, junction: Junction, name:str) -> Any:
        if name == "signed":
            return self.signed
        if name == "length":
            return self.length
        if name == "min_val":
            return self.min_val
        if name == "max_val":
            return self.max_val
        raise AttributeError

    from .module import GenericModule
    class SizeAdaptor(GenericModule):
        def construct(self, input_type: 'Number', output_type: 'Number') -> None:
            if input_type.is_abstract():
                raise SyntaxErrorException("Cannot adapt to numbers from abstract types")
            if output_type.is_abstract():
                raise SyntaxErrorException("Cannot adapt to abstract number types")
            if not isinstance(input_type, Number):
                raise SyntaxErrorException("Can only adapt the size of numbers")
            if not isinstance(output_type, Number):
                raise SyntaxErrorException("Can only adapt the size of numbers")
            self.input = Input(input_type)
            self.output = Output(output_type)
        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            yield InlineExpression(self.output, *self.generate_inline_expression(back_end, target_namespace))
        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"

            ret_val = ""
            need_sign_cast = self.input.signed and not self.output.signed
            need_size_cast = self.input.length > self.output.length
            if need_sign_cast:
                if self.output.signed:
                    ret_val += "signed'("
                else:
                    ret_val += "unsigned'("
            if need_size_cast:
                ret_val += f"{self.output.length}'("
            rhs_name, precedence = self.input.get_rhs_expression(back_end, target_namespace, self.output.get_net_type())
            ret_val += rhs_name
            if need_size_cast:
                precedence = 0
                ret_val += ")"
            if need_sign_cast:
                precedence = 0
                ret_val += ")"
            return ret_val, precedence
        def simulate(self) -> TSimEvent:
            while True:
                yield self.input
                self.output <<= self.input
        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

    def adapt_from(self, input: Junction, implicit: bool) -> Junction:
        input_type = input.get_net_type()
        if not isinstance(input_type, Number):
            return None
        if input_type.is_abstract():
            return None
        if self.is_abstract():
            return None
        if self.min_val > input_type.min_val or self.max_val < input_type.max_val:
            return None
        if self.length >= input_type.length and self.signed == input_type.signed:
            return input
        return Number.SizeAdaptor(input_type = input_type, output_type = self)(input)

    """
    ============================================================================================
    Concatenator and MemberSetter support
    ============================================================================================
    """
    @classmethod
    def create_member_setter(cls) -> Module:
        return Number.MemberSetter()

    @classmethod
    def _overlap(cls, range1 : 'Number.Key', range2: 'Number.Key') -> bool:
        assert not range1.is_sequential and not range2.is_sequential
        assert range1.start >= range1.end
        assert range2.start >= range2.end
        if range1.end > range2.start:
            return False
        if range2.end > range1.start:
            return False
        return True
    @classmethod
    def validate_input_map(cls, input_map: Dict['Number.Key', Junction]) -> bool:
        """
        Returns True if the supplied input map is valid, False otherwise

        input_map can contain:
        - One more more inputs with a sequential key. In that case, the inputs are simply concatenated 
          (in MSB->LSB order) in the order they were inserted into the map. This is the SV {a,b,c} 
          concatenation behavior.
        - One more more inputs with a slice or integer-based keys. In that case the inputs are assigned
          (potentially sign- or zero-extended) to the range specified by the key.
        - The map must contain at least one input.
        It is invalid to have both None-keyed and range-keyed elements in the map.
        """
        if len(input_map) == 0:
            return False
        found_seq= False
        all_seq= True
        for key in input_map.keys():
            if not key.is_sequential:
                all_seq = False
            else:
                found_seq = True
            if not all_seq and found_seq:
                return False
        if all_seq:
            return True
        assert not found_seq
        from itertools import combinations
        for (range1, range2) in combinations(input_map.keys(), 2):
            if cls._overlap(range1, range2):
                return False
        return True
    @classmethod
    def is_sequential_map(cls, input_map: Dict['Number.Key', Junction]) -> bool:
        """
        Returns true if the provided input_map is all sequential

        input_map can contain:
        - One more more inputs with a sequential key. In that case, the inputs are simply concatenated 
          (in MSB->LSB order) in the order they were inserted into the map. This is the SV {a,b,c} 
          concatenation behavior.
        - One more more inputs with a slice or integer-based keys. In that case the inputs are assigned
          (potentially sign- or zero-extended) to the range specified by the key.
        - The map must contain at least one input.
        It is invalid to have both None-keyed and range-keyed elements in the map.
        """
        assert len(input_map) > 0
        for key in input_map.keys():
            if not key.is_sequential:
                return False
        return True
    @classmethod
    def sort_source_keys(cls, input_map: Dict['Number.Key', Junction], back_end: Optional['BackEnd']) -> Tuple['Number.Key']:
        """
        Sort the set of blobs as required by the back-end or for simulation of back_end is None
        """
        assert back_end is None or back_end.language == "SystemVerilog"
        from operator import attrgetter
        if len(input_map) == 1 or cls.is_sequential_map(input_map):
            return tuple(input_map.keys())
        sorted_keys = tuple(sorted(input_map.keys(), key=attrgetter('start'), reverse=True))
        return sorted_keys

    @classmethod
    def concatenated_type(cls, input_map: Dict['Number.Key', Junction]) -> Optional['NetType']:
        """
        Returns the combined type for the given inputs for the keys
        """
        assert len(input_map) > 0
        if not cls.validate_input_map(input_map):
            raise SyntaxErrorException("Can only determine concatenated type if the input map is invalid")
        for junction in input_map.values():
            if not isinstance(junction.get_net_type(), Number):
                raise SyntaxErrorException("Can only determine concatenated type if all constituents are Numbers")
            if junction.get_net_type().is_abstract():
                raise SyntaxErrorException("Can't determine concatenated type if any of the constituents is an abstract Number")
        # Simple assignment: return our input
        if len(input_map) == 1 and first(input_map.keys()).is_sequential:
            return first(input_map.values()).get_net_type()
        # Either multiple sources or the single source has a range assigned to it.
        sorted_keys = cls.sort_source_keys(input_map, back_end = None)
        top_key = first(sorted_keys)
        signed=input_map[top_key].signed # The top-most entry determines the signed-ness of the result
        if not top_key.is_sequential:
            # If the top entry is not sequential, then none of them are: the length of the result is determined by the top position of the top entry
            return Number(length=top_key.start+1, signed=signed)
        # If all entries are sequential, we simply need to add up the lengths of the constituents
        length = 0
        for input in input_map.values():
            length += input.length
        return Number(length=length, signed=signed)

    def compose_concatenated_expression(self, back_end: 'BackEnd', input_map: Dict['Number.Key', Junction], target_namespace: Module) -> Tuple[str, int]:
        def compose_sub_source_expression(sub_port: Junction, section_length: int) -> Tuple[str, int]:
            raw_expr, precedence = sub_port.get_rhs_expression(back_end, target_namespace)
            if sub_port.get_net_type().length == section_length or section_length == self.length:
                # If the request source is of the right length or it covers the whole junction, return it as-is
                return raw_expr, precedence
            elif sub_port.get_net_type().length > section_length:
                raise SyntaxErrorException("Can't assign section of a Number form another, longer Number")
                # Well, in fact we could, but do we want to? That's too close to a coding error to allow it...
                #return f"({raw_expr})[section_length-1:0]"
            else:
                return f"{section_length}'({raw_expr})", 0

        # No source: return a X-assignment
        assert back_end.language == "SystemVerilog"
        if self.is_abstract():
            raise SyntaxErrorException("Can't generate source expression for abstract Numbers")
        if len(input_map) == 0:
            return f"{self.length}'bX", 0

        sorted_keys = self.sort_source_keys(input_map, back_end)
        last_top_idx = self.length
        rtl_parts = []
        for sub_port_key in sorted_keys:
            current_top_idx = sub_port_key.start if not sub_port_key.is_sequential else last_top_idx - 1
            assert current_top_idx < last_top_idx
            if current_top_idx < last_top_idx - 1:
                raise SyntaxErrorException("not all bits in Number have sources")
            sub_port = input_map[sub_port_key]
            last_top_idx = sub_port_key.end if not sub_port_key.is_sequential else last_top_idx - sub_port.length
            slice_length = sub_port_key.length if not sub_port_key.is_sequential else sub_port.length
            rtl_parts.append(compose_sub_source_expression(sub_port, slice_length))
        if last_top_idx > 0:
            raise SyntaxErrorException("not all bits in Number have sources")
        if len(rtl_parts) == 1:
            return rtl_parts[0]
        # For now we're assuming that concatenation returns an UNSIGNED vector independent of the SIGNED-ness of the sources.
        # This is indeed true according to https://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.449.1578&rep=rep1&type=pdf
        ret_val = "{" + ", ".join(rtl_part[0] for rtl_part in rtl_parts) + "}"
        if self.signed:
            return f"signed'({ret_val})", 0
        else:
            return ret_val, back_end.get_operator_precedence("{}")

    def prep_simulate_concatenated_expression(self, input_map: Dict['Number.Key', Junction]) -> Any:
        """
        Returns whatever cached values are needed for quick simulation of concatenation.
        This cached value is stored in the caller (Concatenator) object and is passed in to
        simulate_concatenated_expression below.
        """
        concat_map = []
        sorted_keys = self.sort_source_keys(input_map, None)
        last_top_idx = self.length
        value = 0
        for sub_port_key in sorted_keys:
            current_top_idx = sub_port_key.start if not sub_port_key.is_sequential else last_top_idx - 1
            assert current_top_idx < last_top_idx
            if current_top_idx < last_top_idx - 1:
                raise SyntaxErrorException("not all bits in Number have sources")
            sub_port = input_map[sub_port_key]
            last_top_idx = sub_port_key.end if not sub_port_key.is_sequential else last_top_idx - sub_port.length
            concat_map.append((sub_port, last_top_idx))
        return concat_map

    def simulate_concatenated_expression(self, prep_cache: Any) -> int:
        value = 0
        for sub_port, last_top_idx in prep_cache:
            sub_source_value = sub_port.sim_value
            if sub_source_value is None:
                return None
            value |= sub_source_value << last_top_idx
        return value

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
        def check_all_types_valid():
            if any(net_type is None for net_type in net_types):
                raise SyntaxErrorException("Can't determine union type unless all input types are specified")

        assert len(net_types) > 0
        for net_type in net_types:
            if not isinstance(net_type, Number) and net_type is not None:
                raise SyntaxErrorException("Can only determine union type if all constituents are Numbers")
            if net_type is not None and net_type.is_abstract():
                raise SyntaxErrorException("Can't determine union type if any of the constituents is an abstract Number")
        if operation == "SELECT":
            max_val = None
            min_val = None
            for net_type in net_types:
                if net_type is None:
                    continue
                if max_val is None:
                    max_val = net_type.max_val
                else:
                    max_val = max(max_val, net_type.max_val)
                if min_val is None:
                    min_val = net_type.min_val
                else:
                    min_val = min(min_val, net_type.min_val)
            return Number(max_val=max_val, min_val=min_val)
        elif operation in ("OR", "AND", "XOR"):
            all_signed = True
            all_unsigned = True
            final_signed = False
            max_len = 0
            max_unsigned_len = 0
            for net_type in net_types:
                if net_type is None:
                    continue
                max_len = max(max_len, net_type.length)
                if net_type.signed:
                    all_unsigned = False
                    final_signed = True
                else:
                    all_signed = False
                    max_unsigned_len = max(max_unsigned_len, net_type.length)
            assert not all_signed or not all_unsigned
            if not all_signed and not all_unsigned:
                # FIXME: If some ports are signed and some are unsigned, we might have to sign-extend the result by an extra bit
                #        in case the longest input was unsigned. However I'm not sure that's what we want to do. For now, leave it as-is
                #max_len = max(max_len, max_unsigned_len + 1)
                pass
            ret_val = Number(length=max_len, signed=final_signed)
            #print(f"------ returning {ret_val} for inputs: " + ",".join(str(net_type) for net_type in net_types))
            return ret_val
        elif operation == "SUM":
            max_val = 0
            min_val = 0
            for net_type in net_types:
                if net_type is None:
                    continue
                max_val = max_val + net_type.max_val
                min_val = min_val + net_type.min_val
            return Number(max_val=max_val, min_val=min_val)
        elif operation == "SUB":
            assert len(net_types) == 2
            check_all_types_valid()
            max_val = net_types[0].max_val - net_types[1].min_val
            min_val = net_types[0].min_val - net_types[1].max_val
            return Number(max_val=max_val, min_val=min_val)
        elif operation == "PROD":
            max_val = 1
            min_val = 1
            for net_type in net_types:
                if net_type is None:
                    continue
                max_val = max(
                    max_val * net_type.max_val, 
                    max_val * net_type.min_val, 
                    min_val * net_type.max_val, 
                    min_val * net_type.min_val
                )
                min_val = min(
                    max_val * net_type.max_val, 
                    max_val * net_type.min_val, 
                    min_val * net_type.max_val, 
                    min_val * net_type.min_val
                )
            return Number(max_val=max_val, min_val=min_val)
        elif operation == "SHL":
            assert len(net_types) == 2
            check_all_types_valid()
            if net_types[0].min_val > 0:
                min_val = net_types[0].min_val << net_types[1].min_val
            else:
                min_val = net_types[0].min_val << net_types[1].max_val

            if net_types[0].max_val > 0:
                max_val = net_types[0].max_val << net_types[1].max_val
            else:
                max_val = net_types[0].max_val << net_types[1].min_val
            return Number(max_val=max_val, min_val=min_val)
        elif operation == "SHR":
            assert len(net_types) == 2
            check_all_types_valid()
            if net_types[0].min_val > 0:
                min_val = net_types[0].min_val >> net_types[1].max_val
            else:
                min_val = net_types[0].min_val >> net_types[1].min_val

            if net_types[0].max_val > 0:
                max_val = net_types[0].max_val >> net_types[1].min_val
            else:
                max_val = net_types[0].max_val >> net_types[1].max_val
            return Number(max_val=max_val, min_val=min_val)
        elif operation == "NOT":
            assert len(net_types) == 1
            check_all_types_valid()
            # NOTE: it feels as if this is the same type, but it's not: it's the full binary range of the input, where as min/max for the input could be something smaller
            return Number(length=net_types[0].length, signed=net_types[0].signed)
        elif operation == "NEG":
            assert len(net_types) == 1
            check_all_types_valid()
            return Number(min_val=-net_types[0].max_val, max_val=-net_types[0].min_val)
        elif operation == "ABS":
            assert len(net_types) == 1
            check_all_types_valid()
            if net_types[0].min_val < 0 and net_types[0].max_val > 0:
                min_val = 0
            else:
                min_val = min(abs(net_types[0].min_val), abs(net_types[0].max_val))
            max_val = max(abs(net_types[0].min_val), abs(net_types[0].max_val))
            return Number(min_val=min_val, max_val=max_val)
        else:
            return super().result_type(net_types, operation) # Will raise an exception.


def int_to_const(value: int) -> Tuple[NetType, int]:
    return Number(min_val=value, max_val=value), value

def val_to_sim(value: int) -> int:
    return int(value)

def _str_to_int(value: str) -> Tuple[int, int, bool]:
    """
    Since we don't have custom literals in Python, we'll have to roll our
    custom strings so that we can represent constants of a certain size.

    This is to be able to quickly represent the notion of 4'b0 from Verilog,
    which is very important for quick concatenations, such as [a1, 4'b0, a2].

    The notation used here is identical to Verilogs literals:
    
    [-]<bit width>'[b|o|h|d]<digits>

    What's not supported:
    - missing bit width field.
    """
    negative = False
    if value[0] == '-':
        negative = True
        value = value[1:]
    elif value[0] == '+':
        value = value[1:]
    size_delim = value.find("'")
    if size_delim == -1 or size_delim == 0:
        raise SyntaxErrorException(f"String '{value}' isn't a valid Constant. It misses the ' size delimiter")
    size_field = value[0:size_delim]
    value_field = value[size_delim+1:]
    base_field = value_field[0]
    base_convert = {"d": 10, "D": 10, "h": 16, "H": 16, "o": 8, "O": 8, "b": 2, "B": 2, "x": 16, "X": 16}
    if base_field not in base_convert:
        raise SyntaxErrorException("String '{value}' isn't a valid Constant. It's base '{base_field}' is not valid.")
    base = base_convert[base_field]
    try:
        size = int(size_field)
    except ValueError:
        raise SyntaxErrorException(f"String '{value}' isn't a valid Constant. It's size field '{size_field}' isn't an integer")
    try:
        int_value = int(value_field[1:], base)
    except ValueError:
        raise SyntaxErrorException(f"String '{value}' isn't a valid Constant. It's value field '{value_field}' isn't an integer")
    if negative:
        int_value = -int_value

    if negative:
        max_val = 2 ** (size - 1) - 1
        min_val = -(2 ** (size - 1))
        if int_value > max_val or int_value < min_val:
            raise SyntaxErrorException(f"String '{value}' isn't a valid Constant. It's value field '{value_field}' doesn't fit in the declared size")
    else:
        if int_value > 2 ** size - 1:
            raise SyntaxErrorException(f"String '{value}' isn't a valid Constant. It's value field '{value_field}' doesn't fit in the declared size")
    return (int_value, size, negative)

def str_to_const(value: str) -> Tuple[NetType, int]:
    int_val, size, negative = _str_to_int(value)
    net_type = Number(length=size, signed=negative)
    assert int_val >= net_type.min_val and int_val <= net_type.max_val
    return net_type, int_val

def str_to_sim(value: str) -> int:
    return _str_to_int(value)[0]


def bool_to_const(value: bool) -> Tuple[NetType, int]:
    if value:
        return Unsigned(1), 1
    else:
        return Unsigned(1), 0

from .constant import const_convert_lookup, sim_convert_lookup

const_convert_lookup[int] = int_to_const
const_convert_lookup[str] = str_to_const
const_convert_lookup[bool] = bool_to_const
sim_convert_lookup[int] = val_to_sim
sim_convert_lookup[str] = str_to_sim
sim_convert_lookup[bool] = val_to_sim

def Signed(length: int=None):
    return Number(length=length, signed=True)

def Unsigned(length: int=None):
    return Number(length=length, signed=False)

logic = Number(length=1, signed=False)
ulogic = logic
slogic = Number(length=1, signed=True)

