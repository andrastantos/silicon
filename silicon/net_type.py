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

def behavior(method):
    return method

class NetType(object):
    def __init__(self):
        raise SyntaxErrorException("NetTypes instances should never be created")
    @classmethod
    def generate_type_ref(self, back_end: 'BackEnd') -> str:
        """
        Called during RTL generation on the XNet object to generate the type reference in a wire definition.
        For example 'logic [3:0]' or similar
        """
        raise NotImplementedError

    def generate_port_ref(self, back_end: 'BackEnd') -> str:
        """
        Called during RTL generation to create a port reference for a module.
        For example 'input logic [3:0] or similar
        """
        raise NotImplementedError
    @classmethod
    def is_abstract(cls) -> bool:
        """
        Returns True if the type is abstract, that is it can't be the type of an actual net.
        """
        return False
    @classmethod
    def get_type_name(cls) -> Optional[str]:
        """
        Returns a unique name for the type. This name is used to identify the type, in other words,
        if two type object instances return the same string from get_type_name, they are considered
        to be the same type. Gets frequently overridden in subclasses to provide unique behavior.

        This function is only used to call 'generate' on types that need it (such as interfaces).
        """
        return cls.__name__
    @classmethod
    def generate(cls, netlist: Netlist, back_end: 'BackEnd') -> str:
        """
        Generates definition (if needed) for the type.
        """
        return ""
    @classmethod
    def get_unconnected_value(cls, back_end: 'BackEnd') -> str:
        """
        Returns the unconnected value for the type.
        """
        assert back_end.language == "SystemVerilog"
        return f"{cls.get_num_bits()}'x"
    @classmethod
    def get_default_value(cls, back_end: 'BackEnd') -> str:
        """
        Returns the default value for the type.
        Used mostly for unconnected optional AutoInput ports.
        For example Reg uses this as the reset value if no reset_value is connected.
        """
        assert back_end.language == "SystemVerilog"
        return f"{cls.get_num_bits()}'0"
    @classmethod
    def generate_assign(cls, sink_name: str, source_expression: str, back_end: 'BackEnd') -> str:
        """
        Returns a string-assignment for a sink from the source.
        Normally very simply, but for composite types, it gets a bit more involved.
        """
        assert back_end.language == "SystemVerilog"
        return f"assign {sink_name} = {source_expression};"
    @classmethod
    def get_unconnected_sim_value(cls) -> Any:
        """
        Returns the unconnected value for the type for simulation purposes.
        """
        return None
    @classmethod
    def get_default_sim_value(cls) -> Any:
        """
        Returns the default value for the type for simulation purposes.
        Used mostly for unconnected optional AutoInput ports.
        For example Reg uses this as the reset value if no reset_value is connected.
        """
        raise NotImplementedError
    def validate_sim_value(self, sim_value: Any) -> Any:
        """
        Validates the new sim value before assignment.

        Raises exceptions with approproiate error messages in case of a validation error.
        
        Has the option to change/correct the sim_value prior to assignment.
        
        Returns potentially modified sim_value for assignment.
        """
        return sim_value
    @classmethod
    def get_num_bits(cls) -> int:
        """
        Returns the number of bits needed to represent values of this type
        """
        raise NotImplementedError
    @classmethod
    def adapt_from(cls, input: 'Junction', implicit: bool) -> Optional['Junction']:
        """
        Adapts 'input' to our type, if possible. Might instantiate adaptor modules.
        Returns None if adaptation is not supported, or the Junction represented the
        result of the adaptation.
        """
        return None
    def adapt_to(self, output_type: type, implicit: bool) -> Optional['Junction']:
        """
        Adapts to the given output type, if possible. Might instantiate adaptor modules.
        Returns None if adaptation is not supported, or the Junction represented the
        result of the adaptation.

        If 'implicit' is set to True, it means the adaptation become necessary during automatic
        type-propagation (that is a source is driving a sink of different type). In general
        implicit conversions should be way more restrictive as possible: Python doesn't really
        support implicit conversion and we should follow that tradition. Exceptions would be
        implicitly adapting from a shorted numberic type to a longer one (zero- or sign-extend).
        """
        return None
    @classmethod
    def get_vcd_type(cls) -> str:
        """
        Returns the associated VCD type (one of VAR_TYPES inside vcd.writer.py)
        Must be overwritten for all sub-classes
        """
        raise NotImplementedError
    def convert_to_vcd_type(self) -> Any:
        """
        Converts the native python value of the instance (available in self.sim_state.value) into
        the corresponding VCD-compatible value.
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
        """
        Returns a module that is capable of setting members of the type.
        This module will receive all the members as inputs and will return
        a Junction of the type as its outputs.

        This method gets called for cases such as:
        a[0] = 2
        a[2] = in1
        a[1] = in2 & in3
        """
        raise NotImplementedError

    def setup_junction(self) -> None:
        """
        Called during junction type assignment to give the type a chance to set whatever needs to be set on a junction.

        This is needed because net types are usually injected into the inheritance chain later on, so __init__ for NetTypes
        is not called and certainly wouldn't be called at the right time.

        This function is the chance to set properties on the *instance* as needed.
        """
        pass


    @classmethod
    def same_type_as(cls, other):
        """
        Returns True if the other NetType class or instance is equivalent to this one.
        """
        if not isinstance(other, type):
            other = type(other)
        return cls is other

    def __eq__(self, otheR):
        assert False
    def __ne__(self, other):
        assert False

