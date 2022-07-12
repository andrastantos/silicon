from typing import Tuple, Dict, Optional, Any, Type, Sequence
from .tracer import no_trace
from .netlist import Netlist
from .exceptions import AdaptTypeError, SyntaxErrorException
from .utils import first
from enum import Enum as PyEnum
from types import MethodType

class KeyKind(PyEnum):
    Index = 0
    Member = 1

class NetType(object):
    class Behaviors(object):
        """
        An empty Behaviors class to make sure the inheritance chain for behaviors has always somewhere to terminate
        """
        pass

    def __init__(self):
        self.parent_junction = None
        pass

    def __call__(self, input_port: 'Junction') -> 'Junction':
        from .utils import cast
        return cast(input_port, self)

    def generate_type_ref(self, back_end: 'BackEnd') -> str:
        """
        Generate and return a type reference that is appropriate for the given back-end.

        An example would be 'logic' for a single-bit Number in Verilog
        """
        raise NotImplementedError
    def generate_net_type_ref(self, for_junction: 'Junction', back_end: 'BackEnd') -> str:
        """
        Generate and return a type reference that is suitable to declare a net of the type for the given back-end.

        An example would be 'input logic [7:0]' for a byte-wider input.
        """
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
        """
        Get the value used to denote unconnected values for the given back-end.

        An example would be 3'x for a 3-bit value.

        The default implementation, which creates a single x-value with the number
        of bits needed to represent the values of the type is probably sufficient
        for most derived types.

        The difference between get_default_value and get_unconnected_value is subtle
        but important: most unconnected XNets get assigned the unconnected value.
        However an optional auto-input, if left unconnected uses the default value.
        """
        assert back_end.language == "SystemVerilog"
        return f"{self.get_num_bits()}'hx"
    def get_default_value(self, back_end: 'BackEnd') -> str:
        """
        Get the default used to denote unconnected values for the given back-end.

        An example would be 3'0 for a 3-bit value.

        The default implementation, which creates a 0 value with the number
        of bits needed to represent the values of the type is probably sufficient
        for most derived types.

        The difference between get_default_value and get_unconnected_value is subtle
        but important: most unconnected XNets get assigned the unconnected value.
        However an optional auto-input, if left unconnected uses the default value.
        """
        assert back_end.language == "SystemVerilog"
        return f"{self.get_num_bits()}'h0"
    def generate_assign(self, sink_name: str, source_expression: str, xnet: 'XNet', back_end: 'BackEnd') -> str:
        """
        Generate and return an assignment appropriate for the given back-end

        Parameters:
        sink_name: name of the sink to which the expression to be assigned to
        source_expression: string representation of the source to assign to the sink
        xnet: the XNet for which the assignment is generated
        back_end: described the back-end for which the assignment is generated.
        """
        return f"assign {sink_name} = {source_expression};"
    def get_unconnected_sim_value(self) -> Any:
        """
        Get the value used to denote unconnected values for simulation purposes.

        The default implementation, which returns None is probably sufficient
        for most derived types.

        The difference between get_default_sim_value and get_unconnected_sim_value
        is subtle but important: most unconnected XNets get assigned the unconnected
        value. However an optional auto-input, if left unconnected uses the default
        value.
        """
        raise None
    def get_default_sim_value(self) -> Any:
        """
        Get the default used to denote unconnected values for simulation purposes.

        An example would be 0 for a numerical type.

        The difference between get_default_sim_value and get_unconnected_sim_value
        is subtle but important: most unconnected XNets get assigned the unconnected
        value. However an optional auto-input, if left unconnected uses the default
        value.
        """
        raise NotImplementedError
    def validate_sim_value(self, sim_value: Any, parent_junction: 'Junction') -> Any:
        """
        Validates the new sim value before assignment.

        Raises exceptions with appropriate error messages in case of a validation error.

        Has the option to change/correct the sim_value prior to assignment.

        Returns potentially modified sim_value for assignment.
        """
        return sim_value
    def get_num_bits(self) -> int:
        raise NotImplementedError
    def adapt_from(self, input: Any, implicit: bool, force: bool) -> Any:
        """
        Return the (output of) a converter object that adapts the input to the current type.
        Should raise AdaptTypeError if conversion is not supported.
        Should support trivial conversion where input is of the same type as the current type.
        In these cases, should simply return input.

        It's possible that 'input' is a constant (such as 42) or a sim_value in case of simulation context
        """
        raise AdaptTypeError
    def adapt_to(self, output_type: 'NetType', input: 'Junction', implicit: bool, force: bool) -> Optional['Junction']:
        """
        Return the (output of) a converter object that adapts the current type to the desired output type.
        Should raise AdaptTypeError if conversion is not supported.
        Should support trivial conversion where output_type is of the same type as the current type.
        In these cases, should simply return input.
        """
        raise AdaptTypeError
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
        """
        Create and return a Module that's capable of collecting individual member-assignments to a type.

        Used in (ex.) the following instances:

        a[3] = 1
        a[2:0] = b

        where the generated RTL should become:

        a = {1, b}
        """
        raise NotImplementedError

    def setup_junction(self, junction: 'Junction') -> None:
        """
        Called during junction type assignment to give the type a chance to set whatever needs to be set on a junction.
        This includes things, such as creating member junctions for composites.

        NOTE: by the time setup_junction is called, behaviors (if any) have already been inserted into the class inheritance.
        """
        pass

    def get_behaviors(self) -> Optional[object]:
        """
        Returns an instance contining behavior methods and injected attributes

        Default implementation attempts to instantiate a 'Behaviors' class with no arguments to __init__
        that is defined in net-type.
        """
        try:
            behaviors_class = getattr(type(self), "Behaviors") # This should always succeed
        except:
            raise SyntaxErrorException("The Behaviors class should always be defined in NetTypes, unless something is really screwed up in the inheritance relationships")
        try:
            behaviors_instances = behaviors_class()
            return behaviors_instances
        except:
            return None

    def __eq__(self, other) -> bool:
        """
        Returns True if the other net_type object is equivalent to this one.
        """
        return type(self) == type(other)

    def __ne__(self, other):
        # One usually overrides only __eq__, so provide a default, compatible __ne__ implementation
        return not self == other

