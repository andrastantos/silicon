from .module import Module, InlineBlock, InlineExpression, InlineStatement, InlineComposite, GenericModule, has_port
from typing import Dict, Optional, Tuple, Any, Generator, Union, Sequence
from .port import Junction, Input, Output, Port, AutoInput
from .net_type import NetType, KeyKind
from .exceptions import SyntaxErrorException, SimulationException
from .tracer import no_trace
from collections import OrderedDict
from .utils import first, get_common_net_type, BoolMarker
from .number import logic
from .utils import TSimEvent, is_module

class Select(Module):
    """
    Selector (mux), where the selector is binary encoded
    """
    output_port = Output()
    selector_port = Input()
    default = Input(keyword_only=True)
    def construct(self):
        self.value_ports = OrderedDict()
    
    def __call__(self, *args, **kwargs) -> Union[Port, Tuple[Port]]:
        output_net_type = kwargs.pop("output_net_type", None)
        if output_net_type is not None and has_port(self, "output_port"):
            raise SyntaxErrorException("Gate already has an output port defined. Can't redefine output_net_type")
        return super().__call__(*args, **kwargs)
    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        assert False
    def create_named_port(self, name: str) -> Optional[Port]:
        name_prefix = "value_"
        if name.startswith(name_prefix):
            ret_val = Input()
            # Extract the selector index and put the input into its appropriate collection.
            try:
                selector_idx = int(name[len(name_prefix):])
            except:
                return None
            self.value_ports[selector_idx] = ret_val
            return ret_val
        else:
            return None
    def create_positional_port(self, idx: int) -> Optional[Union[str, Port]]:
        assert idx > 0
        name = f"value_{idx-1}"
        return (name, self.create_named_port(name))

    def generate_output_type(self) -> Optional['Number']:
        value_ports = list(self.value_ports.values())
        if not self.default.is_typeless():
            value_ports.append(self.default)
        all_inputs_specialized = all(tuple(input.is_specialized() for input in self.get_inputs().values()))
        common_net_type = get_common_net_type(value_ports, not all_inputs_specialized)
        if common_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for Select {self}")
        output_type = common_net_type.result_type(tuple(port.get_net_type() for port in value_ports), self.get_operation_str())
        return output_type
    def get_operation_str(self) -> str:
        return "SELECT"

    @property
    def has_default(self) -> bool:
        return self.default.has_driver()
    
    def body(self) -> None:
        if len(self.value_ports) == 0:
            raise SyntaxErrorException(f"Select must have at least one value port {self}")
        if self.has_default:
            raise SyntaxErrorException("Default values for 'Select' modules are not supported: generation of inline verilog is rather difficult for them.")
        new_net_type = self.generate_output_type()
        assert not self.output_port.is_specialized() or self.output_port.get_net_type() == new_net_type
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
                self.output_port <<= self.default
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
        selector_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(self.selector_port, back_end, eq_precedence)

        first = True
        if len(value_ports) == 2 and self.selector_port.get_net_type().length == 1:
            false_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(value_ports[0], back_end, op_precedence)
            true_expression,  _ = target_namespace._impl.get_rhs_expression_for_junction(value_ports[1], back_end, op_precedence)
            ret_val += f"{selector_expression} ? {true_expression} : {false_expression}"
        else:
            for selector_idx in sorted(value_ports.keys()):
                if not first:
                    ret_val += " | "
                    final_precedence = back_end.get_operator_precedence("|",False)
                first = False
                value_port = value_ports[selector_idx]
                value_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(value_port, back_end, op_precedence)
                ret_val += f"{selector_expression} == {selector_idx} ? {value_expression} : {zero}"
            # We don't add the default expression, because that's not the right thing to do: we would have to guard it with an 'else' clause, but that doesn't really exist in a series of and-or gates
            #default_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(self.default, back_end, op_precedence)
            #ret_val += default_expression

        return ret_val, final_precedence

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
    default = Input(keyword_only=True)
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
            The optional kw-only argument 'default' sets the default value
        2. Same as above, but
            selectors are specified by named arguments selector_<idx>
            values are specified by named arguments value_<idx>
            Selectors and their associated values are paired up by the <idx> number
            <idx> starts from 0 and while the parameter order is arbitrary, each selector
            and value must have a pair and the <idx> range must have all values filled in
            The optional kw-only argument 'default' sets the default value
        TODO: these call options need to be implemented:
        3. A number of sequences (lists, tuples), each containing two ports.
            The first port in each sequence is the selector port
            The second port is a value port
            The optional kw-only argument 'default' sets the default value
        4. Two sequences of ports,
            The first sequence containing selector ports
            The second sequence containing value ports 
            The optional kw-only argument 'default' sets the default value
        """
        output_net_type = kwargs.pop("output_net_type", None)
        if output_net_type is not None and has_port(self, "output_port"):
            raise SyntaxErrorException("Gate already has an output port defined. Can't redefine output_net_type")
        return super().__call__(*args, **kwargs)
    @property
    def has_default(self) -> bool:
        return self.default.has_driver()
    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        assert False
    def create_named_port(self, name: str) -> Optional[Port]:
        for name_prefix in ("value_", "selector_"):
            if name.startswith(name_prefix):
                ret_val = Input()
                # Extract the selector index and put the input into its appropriate collection.
                try:
                    selector_idx = int(name[len(name_prefix):])
                except:
                    return None
                collection = getattr(self, name_prefix+"ports")
                collection[selector_idx] = ret_val
                return ret_val
        return None
    def create_positional_port(self, idx: int) -> Optional[Union[str, Port]]:
        if idx % 2 == 0:
            name = f"selector_{idx//2}"
        else:
            name = f"value_{idx//2}"
        return (name, self.create_named_port(name))



    def generate_output_type(self) -> Optional['Number']:
        value_ports = list(self.value_ports.values())
        if not self.default.is_typeless():
            value_ports.append(self.default)
        all_inputs_specialized = all(tuple(input.is_specialized() for input in self.get_inputs().values()))
        if self.has_default:
            all_inputs_specialized &= self.default.is_specialized()
        common_net_type = get_common_net_type(value_ports, not all_inputs_specialized)
        if common_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for Select {self}")
        output_type = common_net_type.result_type(tuple(port.get_net_type() for port in value_ports), self.get_operation_str())
        return output_type
    def get_operation_str(self) -> str:
        return "SELECT"

    
    def body(self) -> None:
        if len(self.value_ports) == 0:
            raise SyntaxErrorException(f"Select must have at least one value port {self}")
        new_net_type = self.generate_output_type()
        assert not self.output_port.is_specialized() or self.output_port.get_net_type() == new_net_type
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
            for selector in self.selector_ports.values():
                if selector.sim_value is None:
                    self.output_port <<= self.default
                    found = True
                    break
                if selector.sim_value != 0:
                    if found:
                        # Due to simultanious changes (that are delayed by epsilon) it's possible that we have multiple inputs set even if that should not occur in a no-delay simulation
                        self.output_port <<= None
                        break
                        #raise SimulationException(f"Multiple selectors set on one-hot encoded selector: {self}")
                    found = True
                    self.output_port <<= self.selector_to_value_map[selector]
            if not found:
                self.output_port <<= self.default

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        self.init_map()
        assert len(self.get_outputs()) == 1
        if self.output_port.is_composite():
            output_port_members = tuple(self.output_port.get_all_member_junctions(add_self=False))
            selector_to_value_member_map = []
            for idx in range(len(output_port_members)):
                selector_to_value_member_map.append(OrderedDict())
            inline_block = InlineComposite(self.output_port)
            for selector, value_port in self.selector_to_value_map.items():
                for idx, member_port in enumerate(value_port.get_all_member_junctions(add_self=False)):
                    selector_to_value_member_map[idx][selector] = member_port

            for idx, output_port in enumerate(output_port_members):
                expression, precedence = self.generate_inline_expression(back_end, target_namespace, output_port_members[idx], selector_to_value_member_map[idx])
                sub_block = InlineExpression(output_port, expression, precedence)
                inline_block.add_member_inlines((sub_block, ))
            yield inline_block
        else:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace, self.output_port, self.selector_to_value_map))

    def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module, output_port: Junction, selector_to_value_map: Dict[Junction, Junction]) -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        ret_val = ""
        zero = f"{output_port.get_net_type().length}'b0"
        op_precedence = back_end.get_operator_precedence("?:",None)
        final_precedence = back_end.get_operator_precedence("|",False)
        for selector, value in selector_to_value_map.items():
            selector_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(selector, back_end, op_precedence)
            value_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(value, back_end, op_precedence)
            ret_val += f"{selector_expression} ? {value_expression} : {zero} | "
        default_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(self.default, back_end, op_precedence)
        ret_val += default_expression
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
                    raise SimulationException(f"SelectFirst is missing input selector for index {idx}")
                try:
                    value = self.value_ports[idx]
                except:
                    raise SimulationException(f"SelectFirst is missing input value for index {idx}")
                if selector.sim_value is None:
                    use_default = False
                    self.output_port <<= self.default
                    break
                if selector.sim_value != 0:
                    use_default = False
                    self.output_port <<= value
                    break
            if use_default:
                self.output_port <<= self.default

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
            selector_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(selector, back_end, op_precedence)
            value_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(value, back_end, op_precedence)
            ret_val += f"{selector_expression} ? {value_expression} : "
        default_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(self.default, back_end, op_precedence)
        ret_val += default_expression
        return ret_val, op_precedence


"""
Concatenator
"""

class Concatenator(Module):
    """
    Generic concatenator object, used (mostly) for RHS concatenations, using the concat function below.

    This module is NOT used for LHS concatenations (a[4:1] = b; a[0] = c).
    Those are handled by type-specific MemberSetter modules.
    """
    output_port = Output()

    def construct(self):
        self.raw_input_map = []
        self.input_map = None
        self.allow_keyed_input = BoolMarker()
    def add_input(self, key: 'Key', junction: Junction) -> None:
        name = f"keyed_input_port_{len(self.raw_input_map)}"
        if has_prot(self, name):
            raise SyntaxErrorException(f"Can't add input to {self} as port name {name} already exists")
        with self.allow_keyed_input:
            port = self._impl._create_named_port(name)
            port <<= junction
        self.raw_input_map.append((key,  getattr(self, name)))
    def create_named_port(self, name: str) -> Optional[Port]:
        if name.startswith("input_port_"):
            return Input()
        elif self.allow_keyed_input and name.startswith("keyed_input_port_"):
            return Input()
        else:
            return None
    def create_positional_port(self, idx: int) -> Optional[Union[str, Port]]:
        name = f"input_port_{idx}"
        return (name, self.create_named_port(name))

    def finalize_input_map(self, common_net_type: object):
        if self.input_map is not None:
            return
        self.input_map = OrderedDict()
        keyed_inputs = set()
        for (raw_key, input) in self.raw_input_map:
            final_key = common_net_type.resolve_key_sequence_for_set(raw_key)
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

    def generate_output_type(self) -> Optional['Number']:
        from .number import Number
        common_net_type = get_common_net_type(self.get_inputs().values())
        if common_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for Concatenator {self}")
        self.finalize_input_map(common_net_type)
        output_type = common_net_type.concatenated_type(self.input_map)
        return output_type

    
    def body(self) -> None:
        new_net_type = self.generate_output_type()
        if new_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for Concatenator {self}")
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

class Reg(Module):
    output_port = Output()
    input_port = Input()
    clock_port = AutoInput(auto_port_names=("clk", "clk_port", "clock", "clock_port"), optional=False)
    reset_port = AutoInput(auto_port_names=("rst", "rst_port", "reset", "reset_port"), optional=True)
    reset_value_port = AutoInput(auto_port_names=("rst_val", "rst_val_port", "reset_value", "reset_value_port"), optional=True)

    def construct(self) -> None:
        self.sync_reset = True
    
    
    def body(self) -> None:
        new_net_type = self.input_port.get_net_type() if self.input_port.is_specialized() else None
        if new_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for Reg {self}")
        assert not self.output_port.is_specialized() or self.output_port.get_net_type() == new_net_type
        if not self.output_port.is_specialized():
            self.output_port.set_net_type(new_net_type)

    
    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        assert False

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        assert len(self.get_outputs()) == 1
        if self.output_port.is_composite():
            if self.input_port.get_net_type() != self.output_port.get_net_type():
                raise SyntaxErrorException(f"Can only register composite types if the input and output types are the same.")
            
            input_members = self.input_port.get_all_member_junctions(add_self=False)
            output_members = self.output_port.get_all_member_junctions(add_self=False)

            if not self.reset_value_port.is_typeless():
                if self.input_port.get_net_type() != self.reset_value_port.get_net_type():
                    raise SyntaxErrorException(f"Can only register composite types if the input and reset_value_port types are the same.")
                reset_value_members = self.input_port.get_all_member_junctions(add_self=False)
            else:
                assert not self.reset_value_port.has_driver(), f"Strange: didn't expect a typeless input to have a driver..."
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
        netlist = target_namespace._impl.netlist
        output_name = target_namespace._impl.get_lhs_name_for_junction(output_port)
        assert output_name is not None
        clk, _ = target_namespace._impl.get_rhs_expression_for_junction(self.clock_port, back_end, back_end.get_operator_precedence("()")) # Get parenthesis around the expression if it's anything complex
        if not self.reset_port.has_driver():
            input_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(input_port, back_end, back_end.get_operator_precedence("<="))
            ret_val = f"always_ff @(posedge {clk}) {output_name} <= {input_expression};\n"
        else:
            rst_expression, rst_precedence = target_namespace._impl.get_rhs_expression_for_junction(self.reset_port, back_end)
            if reset_value_port.has_driver():
                rst_val_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(reset_value_port, back_end, back_end.get_operator_precedence("?:"))
            else:
                rst_val_expression = output_port.get_net_type().get_default_value(back_end)
            input_expression, _ = target_namespace._impl.get_rhs_expression_for_junction(input_port, back_end, back_end.get_operator_precedence("?:"))
            rst_sensitivty_expression, _ = back_end.wrap_expression(rst_expression, rst_precedence, back_end.get_operator_precedence("()"))
            rst_test_expression, _ = back_end.wrap_expression(rst_expression, rst_precedence, back_end.get_operator_precedence("?:"))
            if self.sync_reset:
                ret_val = f"always_ff @(posedge {clk})"
            else:
                ret_val = f"always_ff @(posedge {clk} or {rst_sensitivty_expression})"
            ret_val += f" {output_name} <= {rst_test_expression} ? {rst_val_expression} : {input_expression};\n"
        return ret_val

    def simulate(self) -> TSimEvent:
        def reset():
            if self.reset_value_port.has_driver():
                self.output_port <<= self.reset_value_port
            else:
                self.output_port <<= self.output_port.get_net_type().get_default_sim_value()

        has_reset = self.reset_port.has_driver()
        has_async_reset = not self.sync_reset and has_reset
        while True:
            if has_async_reset:
                yield (self.reset_port, self.clock_port)
            else:
                yield (self.clock_port, )
            # Test for rising edge on clock
            if has_async_reset and self.reset_port.sim_value == 1:
                reset()
            elif self.clock_port.is_sim_edge() and self.clock_port.previous_sim_value == 0 and self.clock_port.sim_value == 1:
                if has_reset and self.reset_port.sim_value == 1:
                    # This branch is never taken for async reset
                    reset()
                else:
                    if self.input_port.is_sim_edge():
                        self.output_port <<= None
                    else:
                        self.output_port <<= self.input_port






