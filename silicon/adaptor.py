from .port import Input, Output
from .module import GenericModule
from .net_type import NetType
from .utils import TSimEvent

class Adaptor(GenericModule):
    def construct(self, output_type: NetType) -> None:
        assert False
        self.output_type = output_type
    def simulate(self) -> TSimEvent:
        assert False
    def is_combinational(self) -> bool:
        """
        Returns True if the module is purely combinational, False otherwise
        """
        return True
