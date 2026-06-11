from .module import GenericModule, InlineBlock, Module, InlineExpression
from .port import Input, Output
from .utils import TSimEvent
from typing import Generator, Tuple

class TrivialAdaptor(GenericModule):
    input_port = Input()
    output_port = Output()
    def construct(self, net_type: 'NetType'):
        # We have to be careful: we insert this adaptor late enough in elaboration that type
        # propagation for the ports is not taking place: we'll have to set the net types
        # manually.
        self.output_port.set_net_type(net_type)
        self.input_port.set_net_type(net_type)
    def get_inline_block(self, back_end: 'BackEnd', target_namespace: 'Module') -> Generator['InlineBlock', None, None]:
        yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))
    def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: 'Module') -> Tuple[str, int]:
        assert back_end.language == "SystemVerilog"
        rhs_name, precedence = self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type())
        return rhs_name, precedence
    def simulate(self) -> TSimEvent:
        while True:
            yield self.input_port
            self.output_port <<= self.input_port.sim_value
    def is_combinational(self) -> bool:
        """
        Returns True if the module is purely combinational, False otherwise
        """
        return True
