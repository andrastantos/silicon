from .port import Junction, Input, JunctionRef
from typing import Optional, Union, Sequence, Any, Dict, Type, Callable
from .net_type import NetType
from .exceptions import SyntaxErrorException, SimulationException
from .module import Module
from .back_end import BackEnd
from .utils import MEMBER_DELIMITER
from .number import logic

class AutoInput(Input):
    """
    An input port variant that supports automatic binding to a set of named nets in the enclosing namespace.
    """
    def __init__(self, net_type: Optional[NetType] = None, parent_module: Module = None, *, keyword_only: bool = False, auto_port_names: Union[str, Sequence[str]], optional: bool = True):
        super().__init__(net_type=net_type, parent_module=parent_module, keyword_only=keyword_only)
        if isinstance(auto_port_names, str):
            auto_port_names = (auto_port_names,)
        self._auto_port_names = tuple(auto_port_names)
        self._optional = optional
        self._candidate = None
        self._auto = True
    def find_cadidates(self):
        assert self.get_parent_module() is not None
        self._candidate = junction_ref(self.get_parent_module()._impl.get_auto_port_to_bind(self._auto_port_names))
    def auto_bind(self):
        # If someone bound to this port, let's not override that
        if self.source is not None:
            return
        if self._candidate is None and not self._optional:
            raise SyntaxErrorException(f"Can't auto-connect port {self}: none of the names {self._auto_port_names} could be found in the enclosing module")
        if self._candidate is not None:
            self.set_source(self._candidate.junction)
    def is_deleted(self) -> bool:
        """
        Returns True if the port (an optional auto-port with no driver) got deleted from the interface
        """
        if self.get_parent_module()._impl.is_top_level():
            return False
        return not self.has_driver() and self._optional

    def generate_interface(self, back_end: 'BackEnd', port_name: str) -> Sequence[str]:
        if self.is_typeless():
            assert self.is_deleted()
            return []

        assert back_end.language == "SystemVerilog"
        if not self.is_composite():
            return [f"{self.get_net_type().generate_net_type_ref(self, back_end)} {port_name}"]
        else:
            ret_val = []
            for member_name, (member_junction, _) in self._member_junctions.items():
                ret_val += member_junction.generate_interface(back_end, f"{port_name}{MEMBER_DELIMITER}{member_name}")
            return ret_val




def junction_ref(junction: Optional[Junction]) -> Optional[JunctionRef]:
    if junction is None:
        return None
    return JunctionRef(junction)

sim_convert_lookup: Dict[Type, Callable] = {}

def sim_const(value: Any, for_junction: 'Junction') -> Any:
    if type(value) in sim_convert_lookup:
        return sim_convert_lookup[type(value)](value, for_junction.get_net_type())
    raise SimulationException(f"Don't know how to convert value {value} of type {type(value)} during simulation", for_junction)


# Pre-defined port types for clk and rst as they are very commonly used
#   ... defined as functions to allow for customization
def ClkPort(
    net_type: Optional[NetType] = logic,
    parent_module: 'Module' = None, *,
    keyword_only: bool = False,
    auto_port_names: Union[str, Sequence[str]] = ("clk", "clk_port", "clock", "clock_port"),
    optional: bool = False
):
    return AutoInput(
        net_type=net_type,
        parent_module=parent_module,
        keyword_only=keyword_only,
        auto_port_names=auto_port_names,
        optional=optional
    )

def ClkEnPort(
    net_type: Optional[NetType] = logic,
    parent_module: 'Module' = None, *,
    keyword_only: bool = False,
    auto_port_names: Union[str, Sequence[str]] = ("clk_en", "clk_en_port", "clock_enable", "clock_enable_port"),
    optional: bool = False
):
    return AutoInput(
        net_type=net_type,
        parent_module=parent_module,
        keyword_only=keyword_only,
        auto_port_names=auto_port_names,
        optional=optional
    )

def RstPort(
    net_type: Optional[NetType] = logic,
    parent_module: 'Module' = None, *,
    keyword_only: bool = False,
    auto_port_names: Union[str, Sequence[str]] = ("rst", "rst_port", "reset", "reset_port"),
    optional: bool = True
):
    return AutoInput(
        net_type=net_type,
        parent_module=parent_module,
        keyword_only=keyword_only,
        auto_port_names=auto_port_names,
        optional=optional
    )

def RstValPort(
    net_type: Optional[NetType] = None,
    parent_module: 'Module' = None, *,
    keyword_only: bool = False,
    auto_port_names: Union[str, Sequence[str]] = ("rst_val", "rst_val_port", "reset_value", "reset_value_port"),
    optional: bool = True
):
    return AutoInput(
        net_type=net_type,
        parent_module=parent_module,
        keyword_only=keyword_only,
        auto_port_names=auto_port_names,
        optional=optional
    )
