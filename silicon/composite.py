from typing import Tuple, Union, Any, Dict, Set, Optional, Generator, Sequence

from .net_type import NetType, KeyKind
from .netlist import Netlist
from .back_end import BackEnd
from .exceptions import SyntaxErrorException, SimulationException
from .module import Module, GenericModule, InlineExpression, InlineBlock, InlineStatement
from .port import Input, Output, Port, Junction
from .tracer import no_trace
from .utils import TSimEvent, MEMBER_DELIMITER
from collections import namedtuple, OrderedDict
from copy import copy
from .number import Unsigned

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

# A decorator for behaviors
class Behavior(object):
    def __init__(self, method):
        self.method = method
def behavior(method):
    return Behavior(method)

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

    def set_behaviors(self, instance: 'Junction'):
        if instance.get_net_type() is not self:
            raise SyntaxErrorException("Can only set behaviors on a Junction that has the same net-type")
        for attr_name in dir(self):
            attr_value = getattr(self,attr_name)
            if isinstance(attr_value, Behavior):
                setattr(instance, attr_name, types.MethodType(attr_value.method, instance))

    def add_member(self, name: str, member: Union[NetType, Reverse]):
        if name in self.members:
            raise SyntaxErrorException(f"Member {name} already exists on composite type {type(self)}")
        if isinstance(member, NetType):
            self.members[name] = (member, False)
        if isinstance(member, Reverse):
            if self._support_reverse:
                self.members[name] = (member.net_type, True)
            else:
                raise SyntaxErrorException(f"Composite type {type(self)} doesn't support reverse members")

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

    def get_unconnected_value(self, back_end: 'BackEnd') -> str:
        raise SyntaxErrorException(f"Unconnected interfaces are not supported")
    def get_default_value(self, back_end: 'BackEnd') -> str:
        raise SyntaxErrorException(f"Unconnected interfaces are not supported")
    def get_unconnected_sim_value(self) -> Any:
        raise SimulationException(f"Unconnected interfaces are not supported")
    def generate_assign(self, sink_name: str, source_expression: str, xnet: 'XNet', back_end: 'BackEnd') -> str:
        ret_val = ""
        for (member_name, (member_type, member_reverse)) in self.get_members().items():
            if member_reverse:
                ret_val += member_type.generate_assign(f"{source_expression}{MEMBER_DELIMITER}{member_name}", f"{sink_name}{MEMBER_DELIMITER}{member_name}", None, back_end) + "\n"
            else:
                ret_val += member_type.generate_assign(f"{sink_name}{MEMBER_DELIMITER}{member_name}", f"{source_expression}{MEMBER_DELIMITER}{member_name}", None, back_end) + "\n"
        return ret_val

    def setup_junction(self, junction: 'Junction') -> None:
        for (member_name, (member_type, member_reverse)) in self.get_members().items():
            junction.create_member_junction(member_name, member_type, member_reverse)
        self.set_behaviors(junction)

class Struct(Composite):
    def __init__(self):
        super().__init__(support_reverse = False)

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
            first_type = net_types[0]
            for net_type in net_types[1:]:
                if not first_type == net_type:
                    raise SyntaxErrorException("SELECT is only supported on structs of the same type")
            return first_type
        else:
            return super().result_type(net_types, operation) # Will raise an exception.

    def __eq__(self, other):
        return self is other or type(self) is type(other)

    class ToNumber(Module):
        input_port = Input()
        output_port = Output()
        def body(self):
            new_net_type = Unsigned(self.input_port.get_net_type().get_num_bits())
            assert not self.output_port.is_specialized()
            self.output_port.set_net_type(new_net_type)

        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            assert len(self.get_outputs()) == 1
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))

        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"
            ret_val = ""
            op_precedence = back_end.get_operator_precedence("{}")
            ret_val += "{"
            xnets = self._impl.netlist.get_xnets_for_junction(self.input_port)
            for idx, (xnet, _) in enumerate(xnets.values()):
                name, _ = xnet.get_rhs_expression(target_namespace, back_end)
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
            input_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(self.input_port, back_end)
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

    @behavior
    def to_number(self) -> Junction:
        return Struct.ToNumber(self)
    @behavior
    def from_number(self, input: Junction) -> None:
        self <<= Struct.FromNumber(self.get_net_type())(input)
class Interface(Composite):
    def __init__(self):
        super().__init__(support_reverse = True)





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
            input_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(self.input_port, back_end, op_precedence)
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
            ret_val += "\n\tassign output_port = '{"
            last_key = len(self.member_names)-1
            for idx, member_name in enumerate(self.member_names):
                ret_val += "{}: {}".format(member_name, member_name)
                if idx != last_key:
                    ret_val += ", "
            ret_val += "}\n"
            ret_val += "endmodule\n\n\n"
            return ret_val
    '''