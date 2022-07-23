from typing import Tuple, Dict, Optional, Any, Type, Sequence, Union
from types import MethodType
from .tracer import no_trace
from .netlist import Netlist
from .exceptions import AdaptTypeError, SyntaxErrorException
from .utils import first, BoolMarker
from enum import Enum as PyEnum

class KeyKind(PyEnum):
    Index = 0
    Member = 1

class NetTypeFactory(object):
    """
    Base type for NetType factories.
    These factories are capable of generating NetTypes, based on parameters.

    The prime example is 'Number': This is not really a NetType, but Number(length=10) is.

    So, Number is actually a NetTypeFactory instance, and it's __new__ returns a - dynamically constructed -
    NetType subclass.

    Other type classes, such as Composites don't work like this: a new Composite is created by the user
    deriving from Composite (or Interface or Struct) and add members that way. Because of this, Composites
    must derive from NetType. These classes are protected against being empty by a trick in __init_subclass__
    and __init__.

    NetTypeFactories can be used to create user-types that depend on some meta-programming parameter.
    An example could be a color structure, where the channel-depth is defined later.

    To create such NetTypes, one creates a sub-class of NetTypeFactory and
    defines the 'construct' classmethod.

    If the 'net_type' parameter is not specified during subclassing, an additional
    class property, called net_type needs to be defines as well.
    """
    def __init_subclass__(cls, /, net_type: Optional['NetTypeMeta'] = None) -> None:
        if net_type is not None:
            cls.net_type = net_type
        cls.instances = {}
    def __new__(cls, *args, **kwargs):
        name, key = cls.construct(None, *args, **kwargs)
        try:
            return cls.instances[key]
        except KeyError:
            obj = type(str(name), (cls.net_type, ), {})
            cls.construct(obj, *args, **kwargs)
            cls.instances[key] = obj
            return obj
    @classmethod
    def construct(cls, net_type, *args, **kwargs):
        """
        If called with net_type == None, returns a name for the created NetType and it's key.
        If called with net_type != None, performs user-defined changes on net_type, based on passed-in parameters. The return value is ignored.

        They 'key' returned *must* compare equal for types that are intended to be equal and not-equal otherwise.
        In most cases, the created type depends only on parameters passed in to 'construct'. In that case, simply returning
        a tuple of all of those parameters as the key ensures appropriate uniqueness.

        The 'name' returned must be a string, or convertible to a string. It doesn't need to be unique, or a valid identifier.
        It in fact could even be the empty string. It is advisable though to give the created NetType a descriptive name as
        debuggers and interactive prompts will use it to display information to the user.
        """
        raise SyntaxErrorException("Generic types can be implemented by inheriting from GenericType, then overriding the construct class-method")

class NetTypeMeta(type):
    assert_on_eq = False

    eq_is_is = BoolMarker()
    def __hash__(self):
        return id(self)
    def __eq__(self, other):
        if NetTypeMeta.eq_is_is:
            return self is other
        if NetTypeMeta.assert_on_eq:
            assert False
        return False

class __FakeInit(object):
    def __init__(self, *args, **kwargs):
        pass

def suppress_init(obj: object) -> object:
    """
    Replaces the __init__ method on the object with one that does nothing
    """
    obj.__class__ = type(obj.__class__.__name__, (__FakeInit, obj.__class__, ), {})
    return obj

class NetType(object, metaclass=NetTypeMeta):
    class Behaviors(object):
        """
        An empty Behaviors class to make sure the inheritance chain for behaviors has always somewhere to terminate
        """

    def __init_subclass__(cls, /, **kwargs):
        for name, value in kwargs.items():
            setattr(cls, name, value)

    def __new__(cls, input_port: Optional['Junction'] = None, /, **kwargs) -> Union['NetType', 'Junction']:
        """
        If called with parameters, this is the explicit type-conversion case.

        If called without parameters, it's (eventually) the port or wire instance creation case.
        In this case we should simply return a NetType instance.
        """
        assert len(kwargs) == 0
        from .utils import cast
        if input_port is None:
            return super().__new__(cls)
        ret_val = cast(input_port, cls)
        # We'll have to do a trick here: ret_val is an OutputPort instance. However, Ports derive from NetType, so
        # if we simply returned it, Python would call __init__ on it, which is not what we want.
        # So we'll create an intermediary type, that overrides __init__ and return that.
        return suppress_init(ret_val)

    @classmethod
    def generate_type_ref(cls, back_end: 'BackEnd') -> str:
        """
        Generate and return a type reference that is appropriate for the given back-end.

        An example would be 'logic' for a single-bit Number in Verilog
        """
        raise NotImplementedError
    @classmethod
    def generate_net_type_ref(cls, for_junction: 'Junction', back_end: 'BackEnd') -> str:
        """
        Generate and return a type reference that is suitable to declare a net of the type for the given back-end.

        An example would be 'input logic [7:0]' for a byte-wider input.
        """
        raise NotImplementedError
    @classmethod
    def get_type_name(cls) -> Optional[str]:
        """
        Returns a unique name for the type. This name is used to identify the type, in other words, if two type object instances return the same string from get_type_name, they are considered to be the same type.
        Gets frequently overridden in subclasses to provide unique behavior.

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
        return f"{cls.get_num_bits()}'hx"
    @classmethod
    def get_default_value(cls, back_end: 'BackEnd') -> str:
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
        return f"{cls.get_num_bits()}'h0"
    @classmethod
    def generate_assign(cls, sink_name: str, source_expression: str, xnet: 'XNet', back_end: 'BackEnd') -> str:
        """
        Generate and return an assignment appropriate for the given back-end

        Parameters:
        -----------
        sink_name: name of the sink to which the expression to be assigned to
        source_expression: string representation of the source to assign to the sink
        xnet: the XNet for which the assignment is generated
        back_end: described the back-end for which the assignment is generated.
        """
        return f"assign {sink_name} = {source_expression};"
    @classmethod
    def get_unconnected_sim_value(cls) -> Any:
        """
        Get the value used to denote unconnected values for simulation purposes.

        The default implementation, which returns None is probably sufficient
        for most derived types.

        The difference between get_default_sim_value and get_unconnected_sim_value
        is subtle but important: most unconnected XNets get assigned the unconnected
        value. However an optional auto-input, if left unconnected uses the default
        value.
        """
        return None
    @classmethod
    def get_default_sim_value(cls) -> Any:
        """
        Get the default used to denote unconnected values for simulation purposes.

        An example would be 0 for a numerical type.

        The difference between get_default_sim_value and get_unconnected_sim_value
        is subtle but important: most unconnected XNets get assigned the unconnected
        value. However an optional auto-input, if left unconnected uses the default
        value.
        """
        raise NotImplementedError
    @classmethod
    def validate_sim_value(cls, sim_value: Any, parent_junction: 'Junction') -> Any:
        """
        Validates the new sim value before assignment.

        Raises exceptions with appropriate error messages in case of a validation error.

        Has the option to change/correct the sim_value prior to assignment.

        Returns potentially modified sim_value for assignment.
        """
        return sim_value
    @classmethod
    def get_num_bits(cls) -> int:
        raise NotImplementedError
    @classmethod
    def adapt_from(cls, input: Any, implicit: bool, force: bool) -> Any:
        """
        Return the (output of) a converter object that adapts the input to the current type.
        Should raise AdaptTypeError if conversion is not supported.
        Should support trivial conversion where input is of the same type as the current type.
        In these cases, should simply return input.

        It's possible that 'input' is a constant (such as 42) or a sim_value in case of simulation context
        """
        raise AdaptTypeError
    @classmethod
    def adapt_to(cls, output_type: 'NetType', input: 'Junction', implicit: bool, force: bool) -> Optional['Junction']:
        """
        Return the (output of) a converter object that adapts the current type to the desired output type.
        Should raise AdaptTypeError if conversion is not supported.
        Should support trivial conversion where output_type is of the same type as the current type.
        In these cases, should simply return input.
        """
        raise AdaptTypeError
    @classmethod
    @property
    def vcd_type(cls) -> str:
        """
        Returns the associated VCD type (one of VAR_TYPES inside vcd.writer.py)
        Must be overwritten for all sub-classes
        """
        raise NotImplementedError
    @classmethod
    def convert_to_vcd_type(cls, value: Any) -> Any:
        """
        Converts the given native python value into the corresponding VCD-compatible value
        Must be overwritten for all sub-classes
        """
        raise NotImplementedError
    @classmethod
    def get_iterator(cls, parent_junction: 'Junction') -> Any:
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

    @classmethod
    def setup_junction(cls, junction: 'Junction') -> None:
        """
        Called during junction type assignment to give the type a chance to set whatever needs to be set on a junction.
        This includes things, such as creating member junctions for composites.

        NOTE: by the time setup_junction is called, behaviors (if any) have already been inserted into the class inheritance.
        """
        pass

    @classmethod
    def get_behaviors(cls) -> Optional[object]:
        """
        Returns an instance containing behavior methods and injected attributes

        Default implementation attempts to instantiate a 'Behaviors' class with no arguments to __init__
        that is defined in net-type.
        """
        try:
            behaviors_class = getattr(cls, "Behaviors") # This should always succeed
        except:
            raise SyntaxErrorException("The Behaviors class should always be defined in NetTypes, unless something is really screwed up in the inheritance relationships")
        if behaviors_class is NetType.Behaviors:
            return None
        return behaviors_class()
