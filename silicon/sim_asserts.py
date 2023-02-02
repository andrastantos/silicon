from .auto_input import ClkPort, RstPort
from .port import Input, EdgeType
from .module import GenericModule
from .exceptions import SimulationException

from inspect import getframeinfo, stack

class GenericAssertOnClk(GenericModule):
    clk = ClkPort()
    rst = RstPort()
    input_port = Input()

    def construct(self, edge: EdgeType, message: str):
        self.edge = edge
        self.message = message

    def simulate(self):
        while True:
            now = yield self.clk
            if self.rst:
                continue
            if self.clk.get_sim_edge() == self.edge:
                if self.input_port != 1:
                    raise SimulationException(f"{self.message} at {now}")

def AssertOnPosClk(assert_wire, message=None):
    if message is None:
        caller = getframeinfo(stack()[1][0])
        message = f"AssertOnPosClk failed at {caller.filename}:{caller.lineno}"

    return GenericAssertOnClk(EdgeType.Positive, message)(assert_wire)

def AssertOnNegClk(assert_wire, message):
    if message is None:
        caller = getframeinfo(stack()[1][0])
        message = f"AssertOnNegClk failed at {caller.filename}:{caller.lineno}"

    return GenericAssertOnClk(EdgeType.Negative, message)(assert_wire)

AssertOnClk = AssertOnPosClk

class GenericAssertAlways(GenericModule):
    input_port = Input()
    rst = RstPort()

    def construct(self, message: str):
        self.message = message

    def simulate(self):
        while True:
            now = yield self.input_port
            if self.rst:
                continue
            if not self.input_port:
                raise SimulationException(f"{self.message} at {now}")

def AssertAlways(assert_wire, message=None):
    if message is None:
        caller = getframeinfo(stack()[1][0])
        message = f"AssertAlways failed at {caller.filename}:{caller.lineno}"

    return GenericAssertAlways(message)(assert_wire)

