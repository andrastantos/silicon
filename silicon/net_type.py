from typing import Tuple, Dict, Optional, Any, Type, Sequence
from .tracer import no_trace
from .netlist import Netlist
from .exceptions import SyntaxErrorException
from .utils import first
from enum import Enum as PyEnum
from types import MethodType

class KeyKind(PyEnum):
    Index = 0
    Member = 1

# A decorator for behaviors
class Behavior(object):
    def __init__(self, method):
        self.method = method
    def apply(self, attr_name, instance):
        setattr(instance, attr_name, MethodType(self.method, instance))

def behavior(method):
    return Behavior(method)

class NetType(object):
    def __init__(self):
        self.parent_junction = None
        pass

    def set_behaviors(self, instance: 'Junction'):
        if instance.get_net_type() is not self:
            raise SyntaxErrorException("Can only set behaviors on a Junction that has the same net-type")
        for attr_name in dir(self):
            attr_value = getattr(self,attr_name)
            if isinstance(attr_value, Behavior):
                attr_value.apply(attr_name, instance)

    def generate_type_ref(self, back_end: 'BackEnd') -> str:
        raise NotImplementedError
    def generate_net_type_ref(self, for_junction: 'Junction', back_end: 'BackEnd') -> str:
        raise NotImplementedError
    def is_abstract(self) -> bool:
        """
        Returns True if the type is abstract, that is it can't be the type of an actual net.
        """
        return False
    def get_type_name(self) -> Optional[str]:
        """
        Returns a unique name for the type. This name is used to identify the type, in other words, if two type object instances return the same string from get_type_name, they are considered to be the same type.
        Gets frequently overridden in subclasses to provide unique behavior.

        This function is only used to call 'generate' on types that need it (such as interfaces).
        """
        return type(self).__name__
    def generate(self, netlist: Netlist, back_end: 'BackEnd') -> str:
        """
        Generates definition (if needed) for the type.
        """
        return ""

    def get_unconnected_value(self, back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return f"{self.get_num_bits()}'x"
    def get_default_value(self, back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return f"{self.get_num_bits()}'0"
    def generate_assign(self, sink_name: str, source_expression: str, xnet: 'XNet', back_end: 'BackEnd') -> str:
        return f"assign {sink_name} = {source_expression};"
    def get_unconnected_sim_value(self) -> Any:
        raise None
    def get_default_sim_value(self) -> Any:
        raise NotImplementedError
    def validate_sim_value(self, sim_value: Any, parent_junction: 'Junction') -> Any:
        """
        Validates the new sim value before assignment.

        Raises exceptions with approproiate error messages in case of a validation error.
        
        Has the option to change/correct the sim_value prior to assignment.
        
        Returns potentially modified sim_value for assignment.
        """
        return sim_value
    def get_num_bits(self) -> int:
        raise NotImplementedError
    def adapt_from(self, input: 'Junction', implicit: bool) -> Optional['Junction']:
        """
        Return None if adaptation is not supported
        """
        return None
    def adapt_to(self, output_type: 'NetType', input: 'Junction', implicit: bool) -> Optional['Junction']:
        """
        Return None if adaptation is not supported
        """
        return None
    @property
    def vcd_type(self) -> str:
        """
        Returns the associated VCD type (one of VAR_TYPES inside vcd.writer.py)
        Must be overwritten for all sub-classes
        """
        raise NotImplementedError
    def convert_to_vcd_type(self, value: Any) -> Any:
        """
        Converts the given native python value into the corresponding VCD-compatible value
        Must be overwritten for all sub-classes
        """
        raise NotImplementedError
    def get_iterator(self, parent_junction: 'Junction') -> Any:
        """
        Returns an iterator for the type (such as one that iterates through all the bits of a number)
        Must be overwritten for all sub-classes
        """
        raise NotImplementedError

    @classmethod
    def result_type(cls, net_types: Sequence[Optional['NetType']], operation: str) -> 'NetType':
        """
        Returns the NetType that can describe any possible result of the specified operation,
        given the paramerters to said operation are (in order) are of the specified types.

        Needs to be overwritten in subclasses to provide meaningful implementation.
        Default is to simply raise a syntax error

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
            CONCAT
            NOT
            NEG
            ABS
        """
        all_net_type_names = " ".join(str(net_type) for net_type in net_types)
        
        raise SyntaxErrorException(f"No result type can be found for the specified set of NetTypes: {all_net_type_names}")

    @classmethod
    def create_member_setter(cls) -> 'Module':
        raise NotImplementedError

    def setup_junction(self, junction: 'Junction') -> None:
        """
        Called during junction type assignment to give the type a chance to set whatever needs to be set on a junction.
        This includes things, such as imbuning junctions with behaviors.
        TODO: maybe Number should use this technique to inject legnth/min/max/signed into the Junction?
        """
        self.set_behaviors(junction)


    def __eq__(self, other) -> bool:
        """
        Returns True if the other net_type object is equivalent to this one.
        """
        return type(self) == type(other)

    def __ne__(self, other):
        # One usually overrides only __eq__, so provide a default, compatible __ne__ implementation
        return not self == other
