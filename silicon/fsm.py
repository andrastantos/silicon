# NOTES:
# We might also need a new selector, that makes choices easier and more explicit. Maybe call it SelectChoice?
# It works the same way as SelectOne, except it constructs the == operations, using the first input.
# Below, I spelled things out using SelectOne though...

from .module import GenericModule, Module
from .port import Input, Output, Wire, Junction
from .auto_input import ClkPort, RstPort, RstValPort
from .primitives import SelectOne, Reg
from .exceptions import SyntaxErrorException
from .utils import is_junction_or_member
from .number import logic
from .constant import get_net_type_for_const
from .back_end import str_to_id
from collections import OrderedDict
from typing import Any, Optional, Tuple
from enum import Enum

def _format_state_name(state: Any):
    if isinstance(state, Enum):
        return state.name
    return str_to_id(state)

def _get_state_name(state: Any) -> str:
    from enum import Enum as PyEnum
    if isinstance(state, PyEnum):
        return state.name
    return str(state)

class FSMLogic(Module):
    state = Input()
    next_state = Output()
    default_state = Input()

    def construct(self) -> None:
        self._state_transition_table = OrderedDict()


    def create_transition(self, current_state: Any, new_state: Any) -> Tuple[Junction, str]:
        if is_junction_or_member(current_state):
            raise SyntaxErrorException(f"Current state must be a constant, not a net.")
        if is_junction_or_member(new_state):
            raise SyntaxErrorException(f"New state must be a constant, not a net.")
        edge = (current_state, new_state)
        #if edge in self._state_transition_table:
        #    raise SyntaxErrorException(f"State transition from {current_state} to {new_state} already exists in FSM {self}")
        input = Input()
        if edge in self._state_transition_table:
            port_name = f"input_{_format_state_name(current_state)}_to_{_format_state_name(new_state)}_{len(self._state_transition_table[edge])}"
            self._state_transition_table[edge].append(input)
        else:
            port_name = f"input_{_format_state_name(current_state)}_to_{_format_state_name(new_state)}"
            self._state_transition_table[edge] = [input,]
        setattr(self, port_name, input)
        return input, port_name

    def add_transition(self, current_state: Any, condition: Junction, new_state: Any) -> None:
        input, _ = self.create_transition(current_state, new_state)
        input <<= condition

    def body(self) -> None:
        # Transform edges to the appropriate format to be able to iterate in the right way
        transitions = OrderedDict()
        for (current_state, new_state), condition_ports in self._state_transition_table.items():
            if current_state not in transitions:
                transitions[current_state] = OrderedDict()
            transitions[current_state][new_state] = condition_ports

        # Generate the outer (current state) and inner (next state) selectors
        next_state_args = []
        for current_state, edges in transitions.items():
            args = []
            for new_state, condition_ports in edges.items():
                for condition_port in condition_ports:
                    args.append(condition_port)
                    args.append(new_state)
            condition_selector = SelectOne(*args, default_port = self.default_state)
            next_state_args.append(self.state == current_state)
            next_state_args.append(condition_selector)
        self.next_state <<= SelectOne(*next_state_args, default_port = self.default_state)

    def draw(self, scope: Module, netlist: 'Netlist', back_end: 'BackEnd', graph: Optional['Digraph'] = None) -> 'Digraph':
        from graphviz import Digraph

        f = Digraph(name = self._impl.get_diagnostic_name()) if graph is None else graph

        f.attr(rankdir='LR', size='8,5')

        # Try to figure out the default port
        default_value, _ = self.default_state.get_rhs_expression(back_end, scope, self.next_state.get_net_type())
        f.node(name="__others__", xlabel="others", shape="point", fillcolor="gray", style="dashed", height="0.2")
        f.node(name=str(default_value), label=str(default_value), shape="circle")
        f.edge("__others__", str(default_value), style="dashed")

        f.attr('node', shape='circle')
        for (current_state, new_state), condition_ports in self._state_transition_table.items():
            for condition_port in condition_ports:
                condition_str, _ = condition_port.get_rhs_expression(back_end, scope, logic)
                f.edge(_get_state_name(current_state), _get_state_name(new_state), label=condition_str)
        return f


class FSM(GenericModule):
    clock_port = ClkPort()
    reset_port = RstPort()
    reset_value = RstValPort()
    state = Output()
    next_state = Output()
    default_state = Input()

    def construct(self, reg: Module = Reg) -> None:
        self._reg = reg
        self.fsm_logic = FSMLogic()
        #self._min_state_val = None
        #self._max_state_val = None
        self._state_type = None
        self._state_net_type = None

    def add_transition(self, current_state: Any, condition: Junction, new_state: Any) -> None:
        # We have to be a little shifty here: can't connect condition directly to the logic instance
        # as that would skip hierarchy levels. We'll have to create an intermediary input port and
        # connect through it.

        if self._state_type is None:
            self._state_type = type(current_state)
        if not isinstance(current_state, self._state_type):
            raise SyntaxErrorException(f"All states of an FSM must of the same type. In this case all are expected to be of {self._state_type}, yet current_state {current_state} is of type {type(current_state)}")
        if not isinstance(new_state, self._state_type):
            raise SyntaxErrorException(f"All states of an FSM must of the same type. In this case all are expected to be of {self._state_type}, yet current_state {new_state} is of type {type(new_state)}")
        if self._state_net_type is None:
            self._state_net_type = get_net_type_for_const(current_state)
        if self._state_net_type is None:
            raise SyntaxErrorException(f"State junction type can't be determined for state value type {self._state_type}")
        current_state_net_type = get_net_type_for_const(current_state)
        new_state_net_type = get_net_type_for_const(new_state)
        self._state_net_type = self._state_net_type.result_type((self._state_net_type, current_state_net_type, new_state_net_type), "SELECT")

        with self._impl._inside:
            logic_input, port_name = self.fsm_logic.create_transition(current_state, new_state)

        input = Input()
        setattr(self, port_name, input)
        input <<= condition

        with self._impl._inside:
            logic_input <<= input

    def body(self) -> None:
        # Create a wire containing the current state (since outputs can't be read within the body)
        #state_type = Number(min_val=self._min_state_val, max_val=self._max_state_val)
        #local_state = Wire(state_type)
        #local_next_state = Wire(state_type)
        local_state = Wire(self._state_net_type)
        local_next_state = Wire(self._state_net_type)

        self.fsm_logic.default_state <<= self.default_state

        local_next_state <<= self.fsm_logic(local_state)

        # Create register
        local_state <<= self._reg(local_next_state)

        # Hook up output ports
        self.next_state <<= local_next_state
        self.state <<= local_state

    def draw(self, scope: Module, netlist: 'Netlist', back_end: 'BackEnd', graph: Optional['Digraph'] = None) -> 'Digraph':
        from graphviz import Digraph

        f = Digraph(name = self._impl.get_diagnostic_name())

        f.attr(rankdir='LR', size='8,5')

        # Try to figure out the reset port

        reset_value, _ = self.reset_value.get_rhs_expression(back_end, scope, self.next_state.get_net_type())
        f.node(name=str(reset_value), xlabel=str(reset_value), shape="point", height="0.2")

        return self.fsm_logic.draw(scope, netlist, back_end, f)