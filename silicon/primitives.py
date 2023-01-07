from .module import Module, InlineBlock, InlineExpression, InlineStatement, InlineComposite, has_port, GenericModule
from typing import Dict, Optional, Tuple, Any, Generator, Union
from .port import Junction, Input, Output, Port, EdgeType, Wire
from .auto_input import ClkPort, ClkEnPort, RstPort, RstValPort
from .exceptions import FixmeException, SyntaxErrorException, SimulationException, InvalidPortError
from collections import OrderedDict
from .utils import ScopedAttr, get_common_net_type
from .number import NumberMeta
from .utils import TSimEvent, is_module

class Select(Module):
    """
    Selector (mux), where the selector is binary encoded
    """
    output_port = Output()
    selector_port = Input()
    default_port = Input(keyword_only=True, default_value=None)
    def construct(self):
        self.value_ports = OrderedDict()

    def __call__(self, *args, **kwargs) -> Union[Port, Tuple[Port]]:
        output_net_type = kwargs.pop("output_net_type", None)
        if output_net_type is not None and has_port(self, "output_port"):
            raise SyntaxErrorException("Gate already has an output port defined. Can't redefine output_net_type")
        return super().__call__(*args, **kwargs)
    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        assert False
    def create_named_port_callback(self, name: str, net_type: Optional['NetType'] = None) -> Optional[Port]:
        name_prefix = "value_"
        if name.startswith(name_prefix):
            ret_val = Input(net_type)
            # Extract the selector index and put the input into its appropriate collection.
            try:
                selector_idx = int(name[len(name_prefix):])
            except:
                raise InvalidPortError()
            self.value_ports[selector_idx] = ret_val
            return ret_val
        else:
            raise InvalidPortError()
    def create_positional_port_callback(self, idx: int, net_type: Optional['NetType'] = None) -> Tuple[str, Port]:
        assert idx > 0
        name = f"value_{idx-1}"
        return (name, self.create_named_port_callback(name, net_type))

    def generate_output_type(self) -> Optional['NumberMeta']:
        value_ports = self.value_ports.values()
        common_net_type = get_common_net_type(value_ports)
        if common_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for Select")
        output_type = common_net_type.result_type(tuple(port.get_net_type() for port in value_ports), self.get_operation_str())
        return output_type
    def get_operation_str(self) -> str:
        return "SELECT"

    def has_default(self) -> bool:
        return self.default_port.has_driver()

    def body(self) -> None:
        if len(self.value_ports) == 0:
            raise SyntaxErrorException(f"Select must have at least one value port")
        if self.has_default():
            raise SyntaxErrorException("Default values for 'Select' modules are not supported: generation of inline verilog is rather difficult for them.")
        new_net_type = self.generate_output_type()
        assert not self.output_port.is_specialized() or self.output_port.get_net_type() is new_net_type
        if not self.output_port.is_specialized():
            self.output_port.set_net_type(new_net_type)

    def simulate(self) -> TSimEvent:
        while True:
            yield self.get_inputs().values()
            if self.selector_port.sim_value is None:
                self.output_port <<= None
                continue
            selected_input_idx = self.selector_port.sim_value
            if selected_input_idx not in self.value_ports:
                self.output_port <<= self.default_port
            else:
                self.output_port <<= self.value_ports[selected_input_idx]

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        assert len(self.get_outputs()) == 1
        if self.output_port.is_composite():
            output_port_members = tuple(self.output_port.get_all_member_junctions(add_self=False))
            value_port_members = []
            for idx in range(len(output_port_members)):
                value_port_members.append(OrderedDict())
            inline_block = InlineComposite(self.output_port)
            for value_port_key, value_port in self.value_ports.items():
                for idx, member_port in enumerate(value_port.get_all_member_junctions(add_self=False)):
                    value_port_members[idx][value_port_key] = member_port

            for idx, output_port in enumerate(output_port_members):
                expression, precedence = self.generate_inline_expression(back_end, target_namespace, output_port_members[idx], value_port_members[idx])
                sub_block = InlineExpression(output_port, expression, precedence)
                inline_block.add_member_inlines((sub_block, ))
            yield inline_block
        else:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace, self.output_port, self.value_ports))

    def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module, output_port: Junction, value_ports: Dict[Any, Junction]) -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        output_type = output_port.get_net_type()

        ret_val = ""
        zero = f"{output_type.length}'b0"
        final_precedence = back_end.get_operator_precedence("?:",None)
        op_precedence = back_end.get_operator_precedence("?:",None)
        eq_precedence = back_end.get_operator_precedence("==",None)
        selector_expression, _ = self.selector_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), eq_precedence)

        first = True
        if len(value_ports) == 2 and self.selector_port.get_net_type().length == 1:
            false_expression, _ = value_ports[0].get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
            true_expression,  _ = value_ports[1].get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
            ret_val += f"{selector_expression} ? {true_expression} : {false_expression}"
        else:
            for selector_idx in sorted(value_ports.keys()):
                if not first:
                    ret_val += " | "
                    final_precedence = back_end.get_operator_precedence("|",False)
                first = False
                value_port = value_ports[selector_idx]
                value_expression, _ = value_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
                ret_val += f"{selector_expression} == {selector_idx} ? {value_expression} : {zero}"
            # We don't add the default expression, because that's not the right thing to do: we would have to guard it with an 'else' clause, but that doesn't really exist in a series of and-or gates
            #default_expression, _ = self.default_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
            #ret_val += default_expression

        return ret_val, final_precedence

    def generate_inline_statement(self, back_end: 'BackEnd', target_namespace: Module, output_port: Junction, value_ports: Dict[Any, Junction]) -> str:
        assert back_end.language == "SystemVerilog"
        output_type = output_port.get_net_type()

        ret_val = "always_comb begin"
        eq_precedence = back_end.get_operator_precedence("==",None)
        selector_expression, _ = self.selector_port.get_rhs_expression(back_end, target_namespace, None, eq_precedence)
        output_str = output_port.get_lhs_name(back_end, target_namespace, allow_implicit=True)

        first = True
        if len(value_ports) == 2 and self.selector_port.get_net_type().length == 1:
            false_expression, _ = value_ports[0].get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type())
            true_expression,  _ = value_ports[0].get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type())
            ret_val += back_end.indent(f"if {selector_expression} begin")
            ret_val += bace_end.indent(f"? {true_expression} : {false_expression}")
        else:
            for selector_idx in sorted(value_ports.keys()):
                if not first:
                    ret_val += " | "
                first = False
                value_port = value_ports[selector_idx]
                value_expression, _ = value_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type())
                ret_val += f"{selector_expression} == {selector_idx} ? {value_expression} : {zero}"
            # We don't add the default expression, because that's not the right thing to do: we would have to guard it with an 'else' clause, but that doesn't really exist in a series of and-or gates
            #default_expression, _ = self.default_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
            #ret_val += default_expression

        ret_val += "end"
        return ret_val


    def is_combinational(self) -> bool:
        """
        Returns True if the module is purely combinational, False otherwise
        """
        return True

class _SelectOneHot(Module):
    """
    One-hot encoded selector base-class
    """
    output_port = Output()
    default_port = Input(keyword_only=True, default_value=None)
    def construct(self):
        self.value_ports = OrderedDict()
        self.selector_ports = OrderedDict()
        self.selector_to_value_map = None

    def __call__(self, *args, **kwargs) -> Union[Port, Tuple[Port]]:
        """
        This type of module accepts several calling mechanisms:
        1. Provide a list of ports, where
            each odd port (1st, 3rd, 5th, etc) is a selector port
            each even port is a value port
            The optional kw-only argument 'default_port' sets the default value
        2. Same as above, but
            selectors are specified by named arguments selector_<idx>
            values are specified by named arguments value_<idx>
            Selectors and their associated values are paired up by the <idx> number
            <idx> starts from 0 and while the parameter order is arbitrary, each selector
            and value must have a pair and the <idx> range must have all values filled in
            The optional kw-only argument 'default_port' sets the default value
        TODO: these call options need to be implemented:
        3. A number of sequences (lists, tuples), each containing two ports.
            The first port in each sequence is the selector port
            The second port is a value port
            The optional kw-only argument 'default_port' sets the default value
        4. Two sequences of ports,
            The first sequence containing selector ports
            The second sequence containing value ports
            The optional kw-only argument 'default_port' sets the default value
        """
        output_net_type = kwargs.pop("output_net_type", None)
        if output_net_type is not None and has_port(self, "output_port"):
            raise SyntaxErrorException("Gate already has an output port defined. Can't redefine output_net_type")
        return super().__call__(*args, **kwargs)

    def has_default(self) -> bool:
        return self.default_port.has_driver()
    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        assert False
    def create_named_port_callback(self, name: str, net_type: Optional['NetType'] = None) -> Optional[Port]:
        for name_prefix in ("value_", "selector_"):
            if name.startswith(name_prefix):
                ret_val = Input(net_type)
                # Extract the selector index and put the input into its appropriate collection.
                try:
                    selector_idx = int(name[len(name_prefix):])
                except:
                    raise InvalidPortError()
                collection = getattr(self, name_prefix+"ports")
                collection[selector_idx] = ret_val
                return ret_val
        raise InvalidPortError()
    def create_positional_port_callback(self, idx: int, net_type: Optional['NetType'] = None) -> Tuple[str, Port]:
        if idx % 2 == 0:
            name = f"selector_{idx//2}"
        else:
            name = f"value_{idx//2}"
        return (name, self.create_named_port_callback(name, net_type))



    def generate_output_type(self) -> Optional['NumberMeta']:
        value_ports = list(self.value_ports.values())
        if self.default_port.is_specialized():
            value_ports.append(self.default_port)
        all_inputs_specialized = all(tuple(input.is_specialized() for input in self.get_inputs().values()))
        if self.has_default():
            all_inputs_specialized &= self.default_port.is_specialized()
        common_net_type = get_common_net_type(value_ports, not all_inputs_specialized)
        if common_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for Select")
        output_type = common_net_type.result_type(tuple(port.get_net_type() for port in value_ports), self.get_operation_str())
        return output_type
    def get_operation_str(self) -> str:
        return "SELECT"


    def body(self) -> None:
        if len(self.value_ports) == 0:
            raise SyntaxErrorException(f"Select must have at least one value port")
        new_net_type = self.generate_output_type()
        assert not self.output_port.is_specialized() or self.output_port.get_net_type() is new_net_type
        if not self.output_port.is_specialized():
            self.output_port.set_net_type(new_net_type)

    def init_map(self) -> None:
        if self.selector_to_value_map is not None:
            return
        self.selector_to_value_map = OrderedDict()
        for idx, value in self.value_ports.items():
            if idx not in self.selector_ports:
                raise SyntaxErrorException(f"Value input index {idx} doesn't have associated selector")
            self.selector_to_value_map[self.selector_ports[idx]] = value

    def is_combinational(self) -> bool:
        """
        Returns True if the module is purely combinational, False otherwise
        """
        return True


class SelectOne(_SelectOneHot):
    """
    One-hot encoded selector
    """
    def simulate(self) -> TSimEvent:
        self.init_map()
        while True:
            yield self.get_inputs().values()
            found = False
            selected_value = None
            for selector in self.selector_ports.values():
                if selector.sim_value is None:
                    self.output_port <<= self.default_port
                    found = True
                    break
                if selector.sim_value != 0:
                    # Normally we don't like several selectors being 1 at the same time (selectors being one-hot), but
                    # if the associated values are the same, that's not an actual problem. The and-or logic behind the
                    # synthesized logic will actually produce the expected value, so let's accept it.
                    if found:
                        if selected_value != self.selector_to_value_map[selector].sim_value:
                            # Due to simultanious changes (that are delayed by epsilon) it's possible that we have multiple inputs set even if that should not occur in a no-delay simulation
                            self.output_port <<= None
                            break
                            #raise SimulationException(f"Multiple selectors set on one-hot encoded selector", self)
                    found = True
                    selected_value = self.selector_to_value_map[selector].sim_value
                    self.output_port <<= self.selector_to_value_map[selector]
            if not found:
                self.output_port <<= self.default_port

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        self.init_map()
        assert len(self.get_outputs()) == 1
        if self.output_port.is_composite():
            output_port_members = tuple(self.output_port.get_all_member_junctions(add_self=False))
            selector_to_value_member_map = []
            default_member_map = []
            for idx in range(len(output_port_members)):
                selector_to_value_member_map.append(OrderedDict())
            inline_block = InlineComposite(self.output_port)
            for selector, value_port in self.selector_to_value_map.items():
                for idx, member_port in enumerate(value_port.get_all_member_junctions(add_self=False)):
                    selector_to_value_member_map[idx][selector] = member_port
            if self.has_default():
                for default_member_port in self.default_port.get_all_member_junctions(add_self=False):
                    default_member_map.append(default_member_port)
            else:
                default_member_map = [None]*len(selector_to_value_member_map)


            for idx, output_port in enumerate(output_port_members):
                expression, precedence = self.generate_inline_expression(back_end, target_namespace, output_port_members[idx], selector_to_value_member_map[idx], default_member_map[idx])
                sub_block = InlineExpression(output_port, expression, precedence)
                inline_block.add_member_inlines((sub_block, ))
            yield inline_block
        else:
            default_member = self.default_port if self.has_default() else None
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace, self.output_port, self.selector_to_value_map, default_member))

    def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module, output_port: Junction, selector_to_value_map: Dict[Junction, Junction], default_member: Optional[Junction]) -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        ret_val = ""
        zero = f"{output_port.get_net_type().length}'b0"
        op_precedence = back_end.get_operator_precedence("?:",None)
        final_precedence = back_end.get_operator_precedence("|",False)
        for selector, value in selector_to_value_map.items():
            selector_expression, _ = selector.get_rhs_expression(back_end, target_namespace, None, op_precedence)
            value_expression, _ = value.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
            ret_val += f"{selector_expression} ? {value_expression} : {zero} | "
        assert default_member is None or default_member.is_specialized()
        if default_member is not None:
            default_expression, _ = default_member.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
            ret_val += default_expression
        else:
            ret_val = ret_val[:-2] # delete the last '|'
        return ret_val, final_precedence

class SelectFirst(_SelectOneHot):
    """
    Priority encoded selector
    """
    def simulate(self) -> TSimEvent:
        self.init_map()
        while True:
            yield self.get_inputs().values()
            use_default = True
            for idx in range(len(self.selector_ports)):
                try:
                    selector = self.selector_ports[idx]
                except:
                    raise SimulationException(f"SelectFirst is missing input selector for index {idx}", self)
                try:
                    value = self.value_ports[idx]
                except:
                    raise SimulationException(f"SelectFirst is missing input value for index {idx}", self)
                if selector.sim_value is None:
                    use_default = False
                    self.output_port <<= self.default_port
                    break
                if selector.sim_value != 0:
                    use_default = False
                    self.output_port <<= value
                    break
            if use_default:
                self.output_port <<= self.default_port

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        #self.init_map()
        assert len(self.get_outputs()) == 1
        if self.output_port.is_composite():
            output_port_members = tuple(self.output_port.get_all_member_junctions(add_self=False))
            value_member_map = []
            for idx in range(len(output_port_members)):
                value_member_map.append(OrderedDict())
            inline_block = InlineComposite(self.output_port)
            for selector, value_port in self.value_ports.items():
                for idx, member_port in enumerate(value_port.get_all_member_junctions(add_self=False)):
                    value_member_map[idx][selector] = member_port

            for idx, output_port in enumerate(output_port_members):
                expression, precedence = self.generate_inline_expression(back_end, target_namespace, value_member_map[idx])
                sub_block = InlineExpression(output_port, expression, precedence)
                inline_block.add_member_inlines((sub_block, ))
            yield inline_block
        else:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace, self.value_ports))

    def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module, value_ports: Dict[int, Junction]) -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        ret_val = ""
        op_precedence = back_end.get_operator_precedence("?:",None)
        # FIXME: we have to make sure we iterate over the selectors in priority order
        for idx in range(len(self.selector_ports)):
            try:
                selector = self.selector_ports[idx]
            except:
                raise SyntaxErrorException(f"SelectFirst is missing input selector for index {idx}")
            try:
                value = value_ports[idx]
            except:
                raise SyntaxErrorException(f"SelectFirst is missing input value for index {idx}")
            selector_expression, _ = selector.get_rhs_expression(back_end, target_namespace, None, op_precedence)
            value_expression, _ = value.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
            ret_val += f"{selector_expression} ? {value_expression} : "
        default_expression, _ = self.default_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
        ret_val += default_expression
        return ret_val, op_precedence


"""
Concatenator
"""

class Concatenator(Module):
    """
    Generic concatenator object, used (mostly) for RHS concatenations, using the concat function below.

    This module is NOT used for LHS concatenations (a[4:1] = b; a[0] = c).
    Those are handled by type-specific PhiSlice modules.
    """
    output_port = Output()

    def construct(self):
        self.raw_input_map = []
        self.input_map = None
        self.allow_keyed_input = False
    def add_input(self, key: 'Key', junction: Junction) -> None:
        name = f"keyed_input_port_{len(self.raw_input_map)}"
        if has_port(self, name):
            raise SyntaxErrorException(f"Can't add input as port. Name '{name}' already exists")
        with ScopedAttr(self, "allow_keyed_input", True):
            port = self.create_named_port(name)
            port <<= junction
        self.raw_input_map.append((key,  getattr(self, name)))
    def create_named_port_callback(self, name: str, net_type: Optional['NetType'] = None) -> Optional[Port]:
        if name.startswith("input_port_"):
            return Input(net_type)
        elif self.allow_keyed_input and name.startswith("keyed_input_port_"):
            return Input(net_type)
        else:
            raise InvalidPortError()
    def create_positional_port_callback(self, idx: int, net_type: Optional['NetType'] = None) -> Tuple[str, Port]:
        name = f"input_port_{idx}"
        return (name, self.create_named_port_callback(name, net_type))

    def finalize_input_map(self, common_net_type: object):
        if self.input_map is not None:
            return
        self.input_map = OrderedDict()
        keyed_inputs = set()
        for (raw_key, input) in self.raw_input_map:
            remaining_key, final_key = common_net_type.resolve_key_sequence_for_set(raw_key)
            if remaining_key is None:
                raise FixmeException(f"We don't yet support slices that can't completely resolve within a single slice. (Example would be Array slice-followed by Number-slice)")
            key = common_net_type.Key(raw_key) # Convert the raw key into something that the common type understands
            if key in self.input_map:
                raise SyntaxErrorException(f"Input key {raw_key} is not unique for concatenator output type {common_net_type}")
            self.input_map[key] = input
            keyed_inputs.add(input)
        for input in self.get_inputs().values():
            if input not in keyed_inputs:
                key = common_net_type.Key() # Should return a unique key object for sequential inputs
                if key in self.input_map:
                    raise SyntaxErrorException(f"Input key {key} is not unique for concatenator output type {common_net_type}")
                self.input_map[key] = input

    def generate_output_type(self) -> Optional['NumberMeta']:
        from .number import Number
        common_net_type = get_common_net_type(self.get_inputs().values())
        if common_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for Concatenator")
        self.finalize_input_map(common_net_type)
        output_type = common_net_type.concatenated_type(self.input_map)
        return output_type


    def body(self) -> None:
        new_net_type = self.generate_output_type()
        if new_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for Concatenator")
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

def concat(*args, **kwargs):
    return Concatenator(*args, **kwargs)

class GenericReg(GenericModule):
    output_port = Output()
    input_port = Input()
    clock_port = ClkPort()
    reset_port = RstPort()
    reset_value_port = RstValPort()
    clock_en = ClkEnPort()

    def construct(self, clk_edge: EdgeType) -> None:
        self.sync_reset = True
        self.clk_edge = clk_edge
        if self.clk_edge not in (EdgeType.Negative, EdgeType.Positive):
            raise SyntaxErrorException(f"Unsupported clock edge: {self.edge}")


    def body(self) -> None:
        new_net_type = self.input_port.get_net_type() if self.input_port.is_specialized() else None
        if new_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for Reg")
        assert not self.output_port.is_specialized() or self.output_port.get_net_type() is new_net_type
        if not self.output_port.is_specialized():
            self.output_port.set_net_type(new_net_type)


    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        assert False

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        assert len(self.get_outputs()) == 1
        if self.output_port.is_composite():
            if self.input_port.get_net_type() is not self.output_port.get_net_type():
                raise SyntaxErrorException(f"Can only register composite types if the input and output types are the same.")

            input_members = self.input_port.get_all_member_junctions(add_self=False)
            output_members = self.output_port.get_all_member_junctions(add_self=False)

            if self.reset_value_port.is_specialized():
                if self.input_port.get_net_type() is not self.reset_value_port.get_net_type():
                    raise SyntaxErrorException(f"Can only register composite types if the input and reset_value_port types are the same.")
                reset_value_members = self.reset_value_port.get_all_member_junctions(add_self=False)
            else:
                assert not self.reset_value_port.has_driver(), f"Strange: didn't expect a non-specialized input to have a driver..."
                # will cause the logic inside generate_inline_statement to go down the proper path to generate default reset values
                reset_value_members = (self.reset_value_port, ) * len(output_members)

            inline_block = InlineComposite(self.output_port)
            for input_member, output_member, reset_value_member in zip(input_members, output_members, reset_value_members):
                statement = self.generate_inline_statement(back_end, target_namespace, output_member, input_member, reset_value_member)
                sub_block = InlineStatement(output_member, statement)
                inline_block.add_member_inlines((sub_block, ))
            yield inline_block
        else:
            yield InlineStatement((self.output_port,), self.generate_inline_statement(back_end, target_namespace, self.output_port, self.input_port, self.reset_value_port))

    def generate_inline_statement(self, back_end: 'BackEnd', target_namespace: Module, output_port: Junction, input_port: Junction, reset_value_port: Junction) -> str:
        assert back_end.language == "SystemVerilog"
        assert is_module(target_namespace)
        output_name = output_port.get_lhs_name(back_end, target_namespace)
        assert output_name is not None
        clk, _ = self.clock_port.get_rhs_expression(back_end, target_namespace, None, back_end.get_operator_precedence("()")) # Get parenthesis around the expression if it's anything complex
        input_expression, input_precedence = input_port.get_rhs_expression(back_end, target_namespace)
        if (self.clk_edge == EdgeType.Negative):
            edge = "negedge"
        elif (self.clk_edge == EdgeType.Positive):
            edge = "posedge"
        else:
            raise SyntaxErrorException(f"Unsupported clock edge: {self.edge}")
        if self.clock_en.has_driver():
            enable_expression, _ = self.clock_en.get_rhs_expression(back_end, target_namespace, None, back_end.get_operator_precedence("?:"))
            input_expression, input_precedence = back_end.wrap_expression(input_expression, input_precedence, back_end.get_operator_precedence("?:"))
            input_expression = f"{enable_expression} ? {input_expression} : {output_name}"
            input_precedence = back_end.get_operator_precedence("?:")
        if not self.reset_port.has_driver():
            input_expression, _ = back_end.wrap_expression(input_expression, input_precedence, back_end.get_operator_precedence("<="))
            ret_val = f"always_ff @({edge} {clk}) {output_name} <= {input_expression};\n"
        else:
            rst_expression, rst_precedence = self.reset_port.get_rhs_expression(back_end, target_namespace)
            if reset_value_port.has_driver():
                rst_val_expression, _ = reset_value_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), back_end.get_operator_precedence("?:"))
            else:
                rst_val_expression = output_port.get_net_type().get_default_value(back_end)
            input_expression, _ = back_end.wrap_expression(input_expression, input_precedence, back_end.get_operator_precedence("?:"))
            rst_sensitivity_expression, _ = back_end.wrap_expression(rst_expression, rst_precedence, back_end.get_operator_precedence("()"))
            rst_test_expression, _ = back_end.wrap_expression(rst_expression, rst_precedence, back_end.get_operator_precedence("?:"))
            if self.sync_reset:
                ret_val = f"always_ff @({edge} {clk})"
            else:
                ret_val = f"always_ff @({edge} {clk} or {rst_sensitivity_expression})"
            ret_val += f" {output_name} <= {rst_test_expression} ? {rst_val_expression} : {input_expression};\n"
        return ret_val

    def simulate(self) -> TSimEvent:
        def reset():
            if self.reset_value_port.has_driver():
                self.output_port <<= self.reset_value_port
            else:
                if self.output_port.is_composite():
                    members = self.output_port.get_all_member_junctions(add_self=False)
                    for member in members:
                        member <<= member.get_net_type().get_default_sim_value()
                else:
                    self.output_port <<= self.output_port.get_net_type().get_default_sim_value()

        has_reset = self.reset_port.has_driver()
        has_async_reset = not self.sync_reset and has_reset
        has_clk_en = self.clock_en.has_driver()
        while True:
            if has_async_reset:
                yield (self.reset_port, self.clock_port)
            else:
                yield (self.clock_port, )
            # Test for rising edge on clock
            if has_async_reset and self.reset_port.sim_value == 1:
                reset()
            else:
                edge_type = self.clock_port.get_sim_edge()
                if edge_type == self.clk_edge:
                    if has_reset and self.reset_port.sim_value == 1:
                        # This branch is never taken for async reset
                        reset()
                    else:
                        if not has_clk_en or self.clock_en.sim_value == 1:
                            if self.output_port.is_composite():
                                out_members = self.output_port.get_all_member_junctions(add_self=False)
                                in_members = self.input_port.get_all_member_junctions(add_self=False)
                                for out_member, in_member in zip(out_members, in_members):
                                    if in_member.get_sim_edge() != EdgeType.NoEdge:
                                        out_member <<= None
                                    else:
                                        out_member <<= in_member
                            else:
                                if self.input_port.get_sim_edge() != EdgeType.NoEdge:
                                    self.output_port <<= None
                                else:
                                    self.output_port <<= self.input_port
                elif edge_type == EdgeType.Undefined:
                    self.output_port <<= None

class PosReg(GenericReg):
    def __new__(cls, *args, **kwargs):
        return Module.__new__(cls, *args, **kwargs)
    def __init__(self, *args, **kwargs):
        super().__init__(EdgeType.Positive)

class NegReg(GenericReg):
    def __new__(cls, *args, **kwargs):
        return Module.__new__(cls, *args, **kwargs)
    def __init__(self, *args, **kwargs):
        super().__init__(EdgeType.Negative)

Reg = PosReg