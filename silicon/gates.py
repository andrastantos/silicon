from .module import Module, InlineBlock, InlineExpression
from typing import Dict, Optional, Tuple, Any, Generator, Union
from .port import Input, Output, Port
from .net_type import NetType
from .number import logic, Number
from .exceptions import SyntaxErrorException
from .tracer import no_trace
from .utils import first, get_common_net_type, TSimEvent, adjust_precision, adjust_precision_sim

def _is_sim_none(arg: Any) -> bool:
    if arg is None:
        return True
    if arg.sim_value is None:
        return True
    if arg.sim_value.value is None:
        return True
    return False

def _sim_value(arg: Any) -> Any:
    try:
        raw_val = arg.sim_value
    except AttributeError:
        raw_val = arg
    try:
        return raw_val.as_number()
    except AttributeError:
        return raw_val
    #if is_junction(arg):
    #    return arg.sim_value
    #return arg

class Gate(Module):
    output_port = Output()

    def construct(self):
        self.max_input_cnt = None
    def generate_output_type(self) -> Optional['Number']:
        from .number import Number
        common_net_type = get_common_net_type(self.get_inputs().values())
        if common_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for gate {self}")
        output_type = common_net_type.result_type(tuple(input.get_net_type() for input in self.get_inputs().values()), self.get_operation_str())
        return output_type
    def get_operation_str(self) -> str:
        raise NotImplementedError
    
    def body(self) -> None:
        new_net_type = self.generate_output_type()
        assert not self.output_port.is_specialized()
        self.output_port.set_net_type(new_net_type)
    def create_positional_port(self, idx: int) -> Optional[Union[str, Port]]:
        name = f"input_port_{idx}"
        return (name, self.create_named_port(name))
    def create_named_port(self, name: str) -> Optional[Port]:
        from .number import Number

        if self.max_input_cnt is not None and len(self.get_inputs()) > self.max_input_cnt:
            return None

        if name.startswith("input_port_"):
            return Input()
        else:
            return None
    
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return input_expression, input_precedence

    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        assert False
    def is_combinational(self) -> bool:
        """
        Returns True if the module is purely combinational, False otherwise
        """
        return True

"""
==========================================================================================================================
=== N-input operations
==========================================================================================================================
"""
class NInputGate(Gate):
    """
    A generic gate implementation for things where 'N' repeated operations over similar structures is supported. Things, such as (A & B & C) or (aa + bb + cc).
    """
    def sim_op(self, next_input: Port, partial_output: Any) -> Any:
        raise NotImplementedError
    def simulate(self) -> TSimEvent:
        target_precision = self.output_port.precision
        while True:
            yield self.get_inputs().values()
            inputs = list(self.get_inputs().values())
            out_val = _sim_value(inputs[0])
            for input in inputs[1:]:
                out_val = self.sim_op(input, out_val)
            self.output_port <<= out_val
    def generate_op(self, back_end: str) -> Tuple[str, int]:
        raise NotImplementedError

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        assert len(self.get_outputs()) == 1
        yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))

    def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        ret_val = ""
        first = True
        op, op_precedence = self.generate_op(back_end)
        for input in self.get_inputs().values():
            if not first:
                ret_val += f" {op} "
            first = False
            input_expression, input_precedence = input.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
            input_expression, _ = self.adjust_fractional(input, input_expression, input_precedence, back_end)
            ret_val += input_expression
        return ret_val, op_precedence

class and_gate(NInputGate):
    def sim_op(self, next_input: Port, partial_output: Any) -> Any:
        next_input = _sim_value(next_input)
        if next_input is None:
            if partial_output == 0:
                return Number.SimValue(0)
            else:
                return None
        if partial_output is None:
            if next_input == 0:
                return Number.SimValue(0)
            else:
                return None
        return next_input & partial_output
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "&", back_end.get_operator_precedence("&", back_end.BINARY)
    def get_operation_str(self) -> str:
        return "AND"
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, self.output_port.precision, back_end)



class or_gate(NInputGate):
    def sim_op(cls, next_input: Port, partial_output: Any) -> Any:
        def all_ones(n):
            if n is None: return None
            return ((n+1) & n == 0) and (n!=0)

        next_input = _sim_value(next_input)
        if next_input is None:
            if all_ones(_sim_value(partial_output)):
                return partial_output
            else:
                return None
        if partial_output is None:
            if all_ones(_sim_value(partial_output)):
                return partial_output
            else:
                return None
        return next_input | partial_output
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "|", back_end.get_operator_precedence("|", back_end.BINARY)
    def get_operation_str(self) -> str:
        return "OR"
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, self.output_port.precision, back_end)

class xor_gate(NInputGate):
    def sim_op(cls, next_input: Port, partial_output: Any) -> Any:
        next_input = _sim_value(next_input)
        if next_input is None or partial_output is None:
            return None
        return next_input ^ partial_output
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "^", back_end.get_operator_precedence("^", back_end.BINARY)
    def get_operation_str(self) -> str:
        return "XOR"
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, self.output_port.precision, back_end)

class sum_gate(NInputGate):
    def sim_op(cls, next_input: Port, partial_output: Any) -> Any:
        next_input = _sim_value(next_input)
        if next_input is None or partial_output is None:
            return None
        return next_input + partial_output
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "+", back_end.get_operator_precedence("+", back_end.BINARY)
    def get_operation_str(self) -> str:
        return "SUM"
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, self.output_port.precision, back_end)

class prod_gate(NInputGate):
    def sim_op(cls, next_input: Port, partial_output: Any) -> Any:
        next_input = _sim_value(next_input)
        if next_input is None or partial_output is None:
            return None
        return next_input * partial_output
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "*", back_end.get_operator_precedence("*", back_end.BINARY)
    def get_operation_str(self) -> str:
        return "PROD"






"""
==========================================================================================================================
=== Unary operations
==========================================================================================================================
"""

class UnaryGate(Gate):
    def construct(self):
        self.max_input_cnt = 1
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        raise NotImplementedError

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        assert len(self.get_outputs()) == 1
        yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))

    def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        ret_val = ""
        op, op_precedence = self.generate_op(back_end)
        ret_val += f" {op} "
        input_expression, input_precedence = self.input_port_0.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
        input_expression, _ = self.adjust_fractional(self.input_port_0, input_expression, input_precedence, back_end)
        ret_val += input_expression
        return ret_val, op_precedence

    def sim_op(cls, input: Port) -> Any:
        raise NotImplementedError
    def simulate(self) -> TSimEvent:
        while True:
            yield self.get_inputs().values()
            self.output_port <<= self.sim_op(self.input_port_0)

class not_gate(UnaryGate):
    def sim_op(self, input: Port) -> Any:
        input_val = _sim_value(input)
        if input_val is None:
            return None
        return Number.SimValue(input_val).invert(self.output_port.get_num_bits())
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "~", back_end.get_operator_precedence("~", back_end.UNARY)
    def get_operation_str(self) -> str:
        return "NOT"
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, self.output_port.precision, back_end)

class neg_gate(UnaryGate):
    def sim_op(cls, input: Port) -> Any:
        input = _sim_value(input)
        if input is None:
            return None
        return -input
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "-", back_end.get_operator_precedence("-", back_end.UNARY)
    def get_operation_str(self) -> str:
        return "NEG"
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, self.output_port.precision, back_end)

class abs_gate(UnaryGate):
    def sim_op(cls, input: Port) -> Any:
        input = _sim_value(input)
        if input is None:
            return None
        return abs(input)
    def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        q_op_precedence = back_end.get_operator_precedence("?:", None)
        op_precedence = max(q_op_precedence, back_end.get_operator_precedence(">", True))
        input_expression, input_precedence = self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
        input_expression, _ = self.adjust_fractional(self.input_port, input_expression, input_precedence, back_end)
        return f"{input_expression} > 1'b0 ? {input_expression} : -{input_expression}", q_op_precedence
    def get_operation_str(self) -> str:
        return "ABS"
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, self.output_port.precision, back_end)

class bool_gate(UnaryGate):
    def sim_op(cls, input: Port) -> Any:
        input = _sim_value(input)
        if input is None:
            return None
        return bool(input)
    def generate_output_type(self) -> Optional['Number']:
        from .number import logic
        return logic
    def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        op_precedence = back_end.get_operator_precedence("==", True)
        input_expression, _ = self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
        return f"{input_expression} == 1'b0", op_precedence





"""
==========================================================================================================================
=== Binary operations
==========================================================================================================================
"""

class BinaryGate(Gate):
    output_port = Output()

    def construct(self):
        self.max_input_cnt = 2

    def generate_op(self, back_end: str) -> Tuple[str, int]:
        raise NotImplementedError

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        assert len(self.get_outputs()) == 1
        yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))

    def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        ret_val = ""
        first = True
        op, op_precedence = self.generate_op(back_end)
        for input in self.get_inputs().values():
            if not first:
                ret_val += f" {op} "
            first = False
            input_expression, input_precedence = input.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence)
            input_expression, _ = self.adjust_fractional(input, input_expression, input_precedence, back_end)
            ret_val += input_expression
        return ret_val, op_precedence
    def sim_op(cls, input_0: Port, input_1: Any) -> Any:
        raise NotImplementedError
    def simulate(self) -> TSimEvent:
        while True:
            yield self.get_inputs().values()
            self.output_port <<= self.sim_op(self.input_port_0, self.input_port_1)

class sub_gate(BinaryGate):
    def sim_op(cls, input_0: Port, input_1: Any) -> Any:
        input_0 = _sim_value(input_0)
        input_1 = _sim_value(input_1)
        if input_0 is None or input_1 is None:
            return None
        return input_0 - input_1
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "-", back_end.get_operator_precedence("-", back_end.BINARY)
    def get_operation_str(self) -> str:
        return "SUB"
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, self.output_port.precision, back_end)

class lshift_gate(BinaryGate):
    def sim_op(cls, input_0: Port, input_1: Any) -> Any:
        input_0 = _sim_value(input_0)
        input_1 = _sim_value(input_1)
        if input_0 is None or input_1 is None:
            return None
        return input_0 << input_1
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        if self.input_port_0.signed:
            return "<<<", back_end.get_operator_precedence("<<<", back_end.BINARY)
        else:
            return "<<", back_end.get_operator_precedence("<<", back_end.BINARY)
    def get_operation_str(self) -> str:
        return "SHL"

class rshift_gate(BinaryGate):
    def sim_op(cls, input_0: Port, input_1: Any) -> Any:
        input_0 = _sim_value(input_0)
        input_1 = _sim_value(input_1)
        if input_0 is None or input_1 is None:
            return None
        return input_0 >> input_1
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        if self.input_port_0.signed:
            return ">>>", back_end.get_operator_precedence(">>>", back_end.BINARY)
        else:
            return ">>", back_end.get_operator_precedence(">>", back_end.BINARY)
    def get_operation_str(self) -> str:
        return "SHR"


class ComparisonGate(BinaryGate):
    def generate_output_type(self) -> Optional['Number']:
        from .number import logic
        return logic

class lt_gate(ComparisonGate):
    def sim_op(cls, input_0: Port, input_1: Any) -> Any:
        input_0 = _sim_value(input_0)
        input_1 = _sim_value(input_1)
        if input_0 is None or input_1 is None:
            return None
        return Number.SimValue.lt(input_0, input_1)
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "<", back_end.get_operator_precedence("<", back_end.BINARY)
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, max(i.precision for i in self.get_inputs().values()), back_end)

class le_gate(ComparisonGate):
    def sim_op(cls, input_0: Port, input_1: Any) -> Any:
        input_0 = _sim_value(input_0)
        input_1 = _sim_value(input_1)
        if input_0 is None or input_1 is None:
            return None
        return Number.SimValue.le(input_0, input_1)
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "<=", back_end.get_operator_precedence("<=", back_end.BINARY)
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, max(i.precision for i in self.get_inputs().values()), back_end)

class eq_gate(ComparisonGate):
    def sim_op(cls, input_0: Port, input_1: Any) -> Any:
        input_0 = _sim_value(input_0)
        input_1 = _sim_value(input_1)
        if input_0 is None or input_1 is None:
            return None
        return Number.SimValue.eq(input_0, input_1)
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "==", back_end.get_operator_precedence("==", back_end.BINARY)
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, max(i.precision for i in self.get_inputs().values()), back_end)

class ne_gate(ComparisonGate):
    def sim_op(cls, input_0: Port, input_1: Any) -> Any:
        input_0 = _sim_value(input_0)
        input_1 = _sim_value(input_1)
        if input_0 is None or input_1 is None:
            return None
        return Number.SimValue.ne(input_0, input_1)
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return "!=", back_end.get_operator_precedence("!=", back_end.BINARY)
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, max(i.precision for i in self.get_inputs().values()), back_end)

class gt_gate(ComparisonGate):
    def sim_op(cls, input_0: Port, input_1: Any) -> Any:
        input_0 = _sim_value(input_0)
        input_1 = _sim_value(input_1)
        if input_0 is None or input_1 is None:
            return None
        return Number.SimValue.gt(input_0, input_1)
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return ">", back_end.get_operator_precedence(">", back_end.BINARY)
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, max(i.precision for i in self.get_inputs().values()), back_end)

class ge_gate(ComparisonGate):
    def sim_op(cls, input_0: Port, input_1: Any) -> Any:
        input_0 = _sim_value(input_0)
        input_1 = _sim_value(input_1)
        if input_0 is None or input_1 is None:
            return None
        return Number.SimValue.ge(input_0, input_1)
    def generate_op(self, back_end: 'BackEnd') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        return ">=", back_end.get_operator_precedence(">=", back_end.BINARY)
    def adjust_fractional(self, input: 'Junction', input_expression: str, input_precedence: int, back_end: 'BackEnd') -> Tuple[str, int]:
        return adjust_precision(input, input_expression, input_precedence, max(i.precision for i in self.get_inputs().values()), back_end)

