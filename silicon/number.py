from typing import Optional, Any, Tuple, Generator, Union, Dict, Set, Sequence, Union
from .exceptions import FixmeException, SyntaxErrorException, SimulationException, AdaptTypeError
from .net_type import NetType, KeyKind, NetTypeFactory, NetTypeMeta
from .module import GenericModule, Module, InlineBlock, InlineExpression
from .port import Input, Output, Junction, Port
from .utils import first, TSimEvent, get_common_net_type, min_none, max_none, adjust_precision, adjust_precision_sim, first_bit_set, Context, NetValue, is_junction_base
from collections import OrderedDict
import re
try:
    from math import prod
except:
    def prod(args):
        p = 1
        for a in args: p *= a
        return a

def __init__mantissa_bits():
    unit_matches = Number.NetValue.__float_parser.match((1.0).hex())
    unit_mantissa = int(unit_matches.group(2).replace(".", ""), 16)
    return unit_mantissa.bit_length()

def is_number(thing: Any) -> bool:
    try:
        return issubclass(thing, Number.Instance)
    except TypeError:
        return False

class NumberMeta(NetTypeMeta):
    pass
class Number(NetTypeFactory):
    @classmethod
    def construct(cls, net_type, length: Optional[int] = None, signed: Optional[bool] = None, min_val: Optional[int] = None, max_val: Optional[int] = None, precision: Optional[int] = None):
        def _calc_metrics():
            kwargs = {}
            try:
                kwargs["min_val"] = int(min_val) if min_val is not None else None
            except ValueError:
                raise SyntaxErrorException("min_val must be an integer, or at least convertible to an int")
            try:
                kwargs["max_val"] = int(max_val) if max_val is not None else None
            except ValueError:
                raise SyntaxErrorException("max_val must be an integer, or at least convertible to an int")
            try:
                kwargs["signed"] = bool(signed) if signed is not None else None
            except ValueError:
                raise SyntaxErrorException("signed must be a bool, or at least convertible to a bool")
            try:
                kwargs["length"] = int(length) if length is not None else None
            except ValueError:
                raise SyntaxErrorException("length must be an integer, or at least convertible to an int")
            try:
                kwargs["precision"] = int(precision) if precision is not None else None
            except ValueError:
                raise SyntaxErrorException("precision must be an integer, or at least convertible to an int")

            if kwargs["precision"] is None:
                kwargs["precision"] = 0
            if kwargs["precision"] < 0:
                raise SyntaxErrorException("Number types must have a non-negative precision")
            if kwargs["length"] is None:
                if kwargs["min_val"] is None or kwargs["max_val"] is None:
                    raise SyntaxErrorException("Number objects must have either their range or their length specified")
                if kwargs["min_val"] > kwargs["max_val"]:
                    raise SyntaxErrorException("The min_val value of a Number object must not be greater than max_val")
                if kwargs["min_val"] < 0: # In theory, we only need the sign bit if min and max straddle 0, but that would leave us with an unsigned representation for negative ranges.
                    kwargs["int_length"] = max(abs(kwargs["max_val"]), abs(kwargs["min_val"] + 1)).bit_length() + 1
                    kwargs["signed"] = True
                else:
                    kwargs["int_length"] = kwargs["max_val"].bit_length()
                    # (0).bit_length() is 0, so let's patch that up
                    if kwargs["int_length"] == 0:
                        kwargs["int_length"] = 1
                    kwargs["signed"] = False
                # Length is integer and fractional part combined
                kwargs["length"] = kwargs["int_length"] + kwargs["precision"]
            else:
                if kwargs["length"] <= 0:
                    raise SyntaxErrorException("Number types must have a positive length")
                kwargs["int_length"] = kwargs["length"] - kwargs["precision"]
                if kwargs["signed"] is None:
                    raise SyntaxErrorException("For Number objects if length is specified, signed must be specified as well")
                if kwargs["signed"]:
                    len_max_val = 2 ** (kwargs["int_length"] - 1) - 1
                    len_min_val = -(2 ** (kwargs["int_length"] - 1))
                else:
                    len_max_val = 2 ** kwargs["int_length"] - 1
                    len_min_val = 0
                if kwargs["max_val"] is None:
                    kwargs["max_val"] = len_max_val
                if kwargs["min_val"] is None:
                    kwargs["min_val"] = len_min_val
                if kwargs["min_val"] < len_min_val:
                    raise SyntaxErrorException("Length and min_val are both specified, but are incompatible")
                if kwargs["max_val"] > len_max_val:
                    raise SyntaxErrorException("Length and max_val are both specified, but are incompatible")
            # Cache maximum and minimum simulation values to speed up value simulation
            kwargs["max_sim_val"] = kwargs["max_val"] << kwargs["precision"] | ((1 << kwargs["precision"]) - 1)
            kwargs["min_sim_val"] = kwargs["min_val"] << kwargs["precision"]
            return kwargs

        kwargs = _calc_metrics()
        precision = kwargs["precision"]
        min_val = kwargs["min_val"]
        max_val = kwargs["max_val"]

        # NOTE: the name of the type could be anything really, doesn't have to be something that's a valid identifier.
        #       This could be important, because we can avoid name-collisions this way.
        if precision != 0:
            type_name = f"Number_{min_val}-{max_val}_{precision}"
        else:
            type_name = f"Number_{min_val}-{max_val}"
        key = (precision, min_val, max_val)
        if net_type is not None:
            for name,value in kwargs.items():
                setattr(net_type, name, value)
        return type_name, key


    class NetValue(NetValue):
        # Used to extract the exact floating point exponent and mantissa from a float.
        # Pre-compiled only once to speed things up a little.
        __float_parser = re.compile("(-?)0x([^p]*)p(.*)")
        # Let's figure out the number of bits in the mantissa and cache it in the class
        # NOTE: This is ugly as hell, but I had to inline everything to make Python happy. What's really going on here is this:
        #           def __init_mantissa_bits():
        #               unit_matches = Number.NetValue.__float_parser.match((1.0).hex())
        #               unit_mantissa = int(unit_matches.group(2).replace(".", ""), 16)
        #               return unit_mantissa.bit_length()
        #           __float_mantissa_bits = __init_mantissa_bits()
        __float_mantissa_bits = int(re.compile("(-?)0x([^p]*)p(.*)").match((1.0).hex()).group(2).replace(".", ""), 16).bit_length()


        def __init__(self, value: Optional[Union[int,'Number.NetValue']]= None, precision: int = 0):
            if isinstance(value, Number.NetValue):
                self.value = value.value
                self.precision = value.precision
            else:
                self.precision = int(precision)
                self.value = int(value)

        @staticmethod
        def _precision_and_value(thing: Union[int, float, 'Number.NetValue', 'Junction']) -> Tuple[int]:
            if isinstance(thing, int):
                return 0, thing
            if isinstance(thing, float):
                if thing == 0.0:
                    return 0, 0

                # Now, pick apart the actual number
                matches = Number.NetValue.__float_parser.match(thing.hex())
                if matches is None:
                    raise ValueError(f"Somehow '{thing}' is not a float I can parse")
                is_positive = matches.group(1) == ''
                mantissa_str = matches.group(2)
                mantissa = int(mantissa_str.replace(".",""), 16) # This is now a fixed point integer where the MSB is the integer part, all other bits are fractional.
                if not is_positive:
                    mantissa = -mantissa
                exponent = int(matches.group(3))
                rightmost_bit_idx = first_bit_set(mantissa)
                leftmost_bit_idx = mantissa.bit_length() - 1

                precision = (Number.NetValue.__float_mantissa_bits - rightmost_bit_idx - 1) - exponent + (Number.NetValue.__float_mantissa_bits - leftmost_bit_idx - 1)
                mantissa >>= rightmost_bit_idx
                if precision < 0:
                    mantissa <<= -precision
                    precision = 0
                return precision, mantissa

            from .gates import _sim_value
            thing = _sim_value(thing)
            if thing is None:
                return None, None
            return thing.precision, thing.value
        @staticmethod
        def _value_in_precision(value: int, precision: int, out_precision: int) -> int:
            if value is None:
                return None
            if precision == out_precision:
                return value
            if precision > out_precision:
                return value >> (precision - out_precision)
            else:
                return value << (out_precision - precision)

        def _coerce_precisions(self, other) -> Tuple[int, int, int]:
            other_precision, other_value = Number.NetValue._precision_and_value(other)
            if other_precision is None or other_value is None:
                return None, None, None
            my_precision = self.precision
            result_precision = max(my_precision, other_precision)
            other_value = Number.NetValue._value_in_precision(other_value, other_precision, result_precision)
            my_value = Number.NetValue._value_in_precision(self.value, my_precision, result_precision)
            return my_value, other_value, result_precision

        def __add__(self, other: Any) -> Any:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value + other_value, result_precision)

        def __sub__(self, other: Any) -> Any:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value - other_value, result_precision)

        def __mul__(self, other: Any) -> Any:
            other_precision, other_value = Number.NetValue._precision_and_value(other)
            my_precision = self.precision
            result_precision = my_precision + other_precision
            my_value = self.value
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value * other_value, result_precision)

        #def __truediv__(self, other: Any) -> Any:
        #def __floordiv__(self, other: Any) -> Any:
        #def __mod__(self, other: Any) -> Any:
        #def __divmod__(self, other: Any) -> Any:
        #def __pow__(self, other: Any, modulo = None) -> Any:

        def __lshift__(self, other: Any) -> Any:
            other_precision, other_value = Number.NetValue._precision_and_value(other)
            if other_precision != 0:
                raise SimulationException(f"Can only shift by integer amount. {other} is potentially fractional.")
            my_precision = self.precision
            my_value = self.value
            if my_value is None or other_value is None:
                return Number.NetValue(None, 0)
            if other_value < 0:
                raise SimulationException(f"Can not shift by negative amount. {other} has a negative value of {other_value}")
            result_precision = my_precision
            return Number.NetValue(my_value << other_value, result_precision)

        def __rshift__(self, other: Any) -> Any:
            other_precision, other_value = Number.NetValue._precision_and_value(other)
            if other_precision != 0:
                raise SimulationException(f"Can only shift by integer amount. {other} is potentially fractional.")
            my_precision = self.precision
            my_value = self.value
            if my_value is None or other_value is None:
                return Number.NetValue(None, 0)
            if other_value < 0:
                raise SimulationException(f"Can not shift by negative amount. {other} has a negative value of {other_value}")
            result_precision = my_precision
            return Number.NetValue(my_value >> other_value, result_precision)

        def __and__(self, other: Any) -> Any:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value & other_value, result_precision)

        def __xor__(self, other: Any) -> Any:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value ^ other_value, result_precision)

        def __or__(self, other: Any) -> Any:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value | other_value, result_precision)

        def __radd__(self, other: Any) -> Any:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(other_value + my_value, result_precision)

        def __rsub__(self, other: Any) -> Any:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(other_value - my_value, result_precision)

        def __rmul__(self, other: Any) -> Any:
            other_precision, other_value = Number.NetValue._precision_and_value(other)
            my_precision = self.precision
            result_precision = my_precision + other_precision
            my_value = self.value
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(other_value * my_value, result_precision)

        #def __rtruediv__(self, other: Any) -> Any:
        #def __rfloordiv__(self, other: Any) -> Any:
        #def __rmod__(self, other: Any) -> Any:
        #def __rdivmod__(self, other: Any) -> Any:
        #def __rpow__(self, other: Any) -> Any:

        def __rlshift__(self, other: Any) -> Any:
            other_precision, other_value = Number.NetValue._precision_and_value(other)
            my_precision = self.precision
            if my_precision != 0:
                raise SimulationException(f"Can only shift by integer amount. {self} is potentially fractional.")
            my_value = self.value
            if my_value is None or other_value is None:
                return Number.NetValue(None, 0)
            if my_value < 0:
                raise SimulationException(f"Can not shift by negative amount. {self} has a negative value of {my_value}")
            result_precision = other_precision
            return Number.NetValue(other_value << my_value, result_precision)

        def __rrshift__(self, other: Any) -> Any:
            other_precision, other_value = Number.NetValue._precision_and_value(other)
            my_precision = self.precision
            if my_precision != 0:
                raise SimulationException(f"Can only shift by integer amount. {self} is potentially fractional.")
            my_value = self.value
            if my_value is None or other_value is None:
                return Number.NetValue(None, 0)
            if my_value < 0:
                raise SimulationException(f"Can not shift by negative amount. {self} has a negative value of {my_value}")
            result_precision = other_precision
            return Number.NetValue(other_value >> my_value, result_precision)

        def __rand__(self, other: Any) -> Any:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(other_value & my_value, result_precision)

        def __rxor__(self, other: Any) -> Any:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(other_value ^ my_value, result_precision)

        def __ror__(self, other: Any) -> Any:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(other_value | my_value, result_precision)

        def __neg__(self) -> Any:
            if self.value is None:
                return Number.NetValue(None, self.precision)
            return Number.NetValue(-self.value, self.precision)

        def __pos__(self) -> Any:
            return self.value

        def __abs__(self) -> Any:
            if self.value is None:
                return Number.NetValue(None, self.precision)
            return Number.NetValue(abs(self.value), self.precision)

        def __invert__(self) -> Any:
            raise SyntaxErrorException(f"It's not really possible to invert a Number.NetValue without knowing it's length. Use the 'invert' method instead of the ~ operator if you really need this functionality.")
            #if self.value is None:
            #    return Number.NetValue(None, self.precision)
            #return Number.NetValue(~self.value, self.precision)

        def invert(self, length: int) -> Any:
            if self.value is None:
                return Number.NetValue(None, self.precision)
            # Pythons binary negation operator is pretty lame: it apparently computes -x-1,
            # which is not quite the same when doing fixed-width binary numbers
            all_ones = (1 << length) - 1
            return Number.NetValue(self.value ^ all_ones, self.precision)


        #def __complex__(self) -> Any:

        def __int__(self) -> Any:
            if self.value is None:
                return None
            return self.value >> self.precision

        def __long__(self) -> Any:
            if self.value is None:
                return None
            return self.value >> self.precision

        def __float__(self) -> Any:
            if self.value is None:
                return None
            return self.value / (1 << self.precision)

        def __index__(self) -> Any:
            return self.__int__()

        def __bool__(self) -> bool:
            return bool(self.value)

        def __lt__(self, other: Any) -> bool:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return False
            return my_value < other_value

        def __le__(self, other: Any) -> bool:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return False
            return my_value <= other_value

        def __eq__(self, other: Any) -> bool:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return False
            return my_value == other_value

        def __ne__(self, other: Any) -> bool:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return False
            return my_value != other_value

        def __gt__(self, other: Any) -> bool:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return False
            return my_value > other_value

        def __ge__(self, other: Any) -> bool:
            my_value, other_value, result_precision = self._coerce_precisions(other)
            if my_value is None or other_value is None:
                return False
            return my_value >= other_value

        #def __round__(self, ndigits):
        #def __trunc__(self):
        #def __floor__(self):
        #def __ceil__(self):

        @staticmethod
        def lt(self, other: Any) -> Any:
            if isinstance(self, Number.NetValue):
                my_value, other_value, result_precision = self._coerce_precisions(other)
            elif isinstance(other, Number.NetValue):
                other_value, my_value, result_precision = other._coerce_precisions(self)
            else:
                raise SyntaxErrorException(f"Cant compare values if neither are an instance of Number.NetValue")
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value < other_value, 0)

        @staticmethod
        def le(self, other: Any) -> Any:
            if isinstance(self, Number.NetValue):
                my_value, other_value, result_precision = self._coerce_precisions(other)
            elif isinstance(other, Number.NetValue):
                other_value, my_value, result_precision = other._coerce_precisions(self)
            else:
                raise SyntaxErrorException(f"Cant compare values if neither are an instance of Number.NetValue")
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value <= other_value, 0)

        @staticmethod
        def eq(self, other: Any) -> Any:
            if isinstance(self, Number.NetValue):
                my_value, other_value, result_precision = self._coerce_precisions(other)
            elif isinstance(other, Number.NetValue):
                other_value, my_value, result_precision = other._coerce_precisions(self)
            else:
                raise SyntaxErrorException(f"Cant compare values if neither are an instance of Number.NetValue")
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value == other_value, 0)

        @staticmethod
        def ne(self, other: Any) -> Any:
            if isinstance(self, Number.NetValue):
                my_value, other_value, result_precision = self._coerce_precisions(other)
            elif isinstance(other, Number.NetValue):
                other_value, my_value, result_precision = other._coerce_precisions(self)
            else:
                raise SyntaxErrorException(f"Cant compare values if neither are an instance of Number.NetValue")
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value != other_value, 0)

        @staticmethod
        def gt(self, other: Any) -> Any:
            if isinstance(self, Number.NetValue):
                my_value, other_value, result_precision = self._coerce_precisions(other)
            elif isinstance(other, Number.NetValue):
                other_value, my_value, result_precision = other._coerce_precisions(self)
            else:
                raise SyntaxErrorException(f"Cant compare values if neither are an instance of Number.NetValue")
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value > other_value, 0)

        @staticmethod
        def ge(self, other: Any) -> Any:
            if isinstance(self, Number.NetValue):
                my_value, other_value, result_precision = self._coerce_precisions(other)
            elif isinstance(other, Number.NetValue):
                other_value, my_value, result_precision = other._coerce_precisions(self)
            else:
                raise SyntaxErrorException(f"Cant compare values if neither are an instance of Number.NetValue")
            if my_value is None or other_value is None:
                return Number.NetValue(None, result_precision)
            return Number.NetValue(my_value >= other_value, 0)


        def as_number(self) -> 'Number.NetValue':
            return self


        def __hash__(self):
            return hash(self.value) | hash(self.precision)

        def __str__(self) -> str:
            if self.precision == 0:
                return str(self.value)
            return str(self.value / (1 << self.precision))
        def __format__(self, format_spec) -> str:
            if self.precision == 0:
                return format(self.value, format_spec)
            return format(self.value / (1 << self.precision), format_spec)


    class Accessor(GenericModule):
        """
        Accessor instances are used to implement the following constructs:

        b <<= a[3]
        b <<= a[3:0]
        b <<= a[3:0][2]

        They are instantiated from Number.get_slice and Number.get_rhs_slicer.

        TODO: get_slice will need review
        """
        def construct(self, slice: Union[int, slice], number: 'NumberMeta') -> None:
            self.key = Number.Instance.Key(slice)
            self.input_port = Input(number)
            # At least in SystemVerilog slice always returns unsigned.
            # That I think makes more sense so I'll implement it that way here too.
            # This of course means that signed_number[3:0] for a 4-bit signed is not a no-op!
            # This is listed as a gottcha here: https://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.449.1578&rep=rep1&type=pdf
            #self.output_port = Output(Number(length=self.key.length, signed=number.signed))
            self.output_port = Output(Number(length=self.key.length, signed=False))
        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))
        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"
            input_type = self.input_port.get_net_type()

            # In Verilog we represent fractional types as simple bit-vectors, so the ranges must start from 0 for the right-most (fractional) bit-position.
            start = self.key.start + input_type.precision
            end = self.key.end + input_type.precision
            if input_type.length == 1:
                if start != 0 or end != 0:
                    raise SyntaxErrorException("Can't access sections of single-bit number outside bit 0")
                # Apparently Verilog really doesn't like cascaded [] expressions. So we explicitly disallow it
                return self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), allow_expression = False)
            op_precedence = back_end.get_operator_precedence("[]")
            # Apparently Verilog really doesn't like cascaded [] expressions. So we explicitly disallow it
            rhs_name, _ = self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type(), op_precedence, allow_expression = False)
            if self.key.start > self.input_port.get_net_type().length:
                raise FixmeException("Accessing slices of a Number outside it's length is not yet supported!!")
            if end == start:
                return f"{rhs_name}[{start}]", op_precedence
            else:
                return f"{rhs_name}[{start}:{end}]", op_precedence

        @staticmethod
        def static_sim(in_val: int, key: 'Number.Instance.Key', precision: int):
            # In simulation we represent fractional types as integers, so the ranges must start from 0 for the right-most (fractional) bit-position.
            start = key.start + precision
            end = key.end + precision
            shift = end
            mask = (1 << (start - end + 1)) - 1
            if in_val is None:
                out_val = None
            else:
                out_val = (in_val >> shift) & mask
            return out_val

        def simulate(self) -> TSimEvent:
            input_type = self.input_port.get_net_type()

            # In simulation we represent fractional types as integers, so the ranges must start from 0 for the right-most (fractional) bit-position.
            start = self.key.start + input_type.precision
            end = self.key.end + input_type.precision

            shift = end
            mask = (1 << (start - end + 1)) - 1
            while True:
                yield self.input_port
                in_val = self.input_port.sim_value
                if in_val is None:
                    out_val = None
                else:
                    out_val = (in_val >> shift) & mask
                self.output_port <<= out_val
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            assert False
        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

    class Iterator(object):
        def __init__(self, net_type: 'NumberMeta', junction: Junction):
            self.parent_junction = junction
            self.idx = 0
            self.length = net_type.length
        def __next__(self):
            if self.idx == self.length:
                raise StopIteration
            ret_val = self.parent_junction[self.idx]
            self.idx += 1
            return ret_val


    from .module import GenericModule
    class SizeAdaptor(GenericModule):
        def construct(self, input_type: 'NumberMeta', output_type: 'NumberMeta') -> None:
            if not is_number(input_type):
                raise SyntaxErrorException("Can only adapt the size of numbers")
            if not is_number(output_type):
                raise SyntaxErrorException("Can only adapt the size of numbers")
            self.input_port = Input(input_type)
            self.output_port = Output(output_type)
        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))
        def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
            assert back_end.language == "SystemVerilog"

            ret_val = ""
            need_sign_cast = self.input_port.signed and not self.output_port.signed
            need_int_size_cast = self.input_port.get_net_type().int_length > self.output_port.get_net_type().int_length
            need_fract_size_cast = self.input_port.precision != self.output_port.precision
            if need_int_size_cast:
                ret_val += f"{self.output_port.length}'("
            rhs_name, precedence = self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type())
            rhs_name, precedence = adjust_precision(self.input_port, rhs_name, precedence, self.output_port.precision, back_end)
            ret_val += rhs_name
            if need_int_size_cast:
                precedence = 0
                ret_val += ")"
            if need_sign_cast:
                precedence = 0
                if self.output_port.signed:
                    ret_val += back_end.signed_cast(ret_val)
                else:
                    ret_val += back_end.unsigned_cast(ret_val)
            return ret_val, precedence
        def simulate(self) -> TSimEvent:
            while True:
                yield self.input_port
                self.output_port <<= adjust_precision_sim(self.input_port.sim_value, self.input_port.precision, self.output_port.precision)
        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return True

    class Instance(NetType, metaclass=NumberMeta):
        """
        Number is a range-tracking, fractional bit-vector, the basic type of Silicon.

        It has a minimum and a maximum value, from which the number of bits
        required for representing that range can be derived.

        It is also capable of representing (fixed point) fractional numbers. It tracks
        the 'precision', which is the number of bits after the fractional point.

        If the range contains negative numbers, the representation is 2's complement.
        If the range is non-negative, an unsigned representation is used.

        The 'length' member contains the total number of bits, fractional and integer.
        The 'min_val' and 'max_val' members identify the minimum and maximum *integer* values, the type can have.
        The actual maximum value is max_val, plus all-1-s in the fractional part.

        NOTE: range is inclusive because Pythons 'range' concept (stop is not in the range, but start is) is
        just too obnoxious to use

        NOTE: negative slice-indices are couting backwards from the fractional point. That is a[-1] is the first fractional bit.

        NOTE: as of now, only ranges that are greater then one are supported. For example a range from 0 to 0.125 is not supported
            even though it should be perfectly valid to do so. This causes complications for floating-point constant representation
            among other thigs.
        """

        # The associated VCD type (one of VAR_TYPES inside vcd.writer.py)
        vcd_type: str = 'wire'

        class Key(object):
            def __init__(self, thing: Union[int, slice, None] = None):
                if thing is None:
                    # We need to create a sequential key
                    self.is_sequential = True
                    return
                try:
                    thing = int(thing)
                    self.start = thing
                    self.end = thing
                    self.is_sequential = False
                    return
                except TypeError:
                    pass
                try:
                    start = int(thing.start)
                    end = int(thing.stop)
                    step = thing.step
                    if step is not None:
                        step = int(step)
                    if step is not None and step != 1 and step != -1:
                        raise SyntaxErrorException("Number slices must be contiguous")
                    single_element = start == end
                    ascending = start < end
                    if ascending and step is None or step == 1:
                        # Python-style, ascending range: higher bound is exclusive
                        self.end = start
                        self.start = end-1
                    elif ascending and step == -1:
                        # Verilog-style, ascending range: higher bound is inclusive
                        self.end = start
                        self.start = end
                    elif not ascending and step is None or step == -1:
                        # Verilog-style, descending range: higher bound is inclusive
                        self.end = end
                        self.start = start
                    elif not ascending and step == -1:
                        # Python-style, descending range: higher bound is exclusive
                        self.end = end-1
                        self.start = start
                    elif single_element:
                        # We are going to assume that this is Verilog-style
                        self.start = start
                        self.end = end
                    else:
                        assert False
                    self.is_sequential = False
                    return
                except AttributeError:
                    pass
                raise SyntaxErrorException("Number slices must be integers or integer ranges.")
            @property
            def length(self) -> int:
                return self.start - self.end + 1
            def apply(self, inner_key: 'Number.Instance.Key') -> 'Number.Instance.Key':
                result = Number.Instance.Key(0) # Just to have it initialized. We'll override members below...
                result.end = self.end + inner_key.end
                result.start = self.end + inner_key.start
                if result.end > self.start or result.start > self.start:
                    raise SyntaxErrorException("Slice of slices is out of bounds. The inner slice cannot fit in the outer one")
                return result

        # This method can only be re-enabled when Number becomes the base of Junction.
        # In that case, it would be called on the instance, and could also provide value info.
        #def __str__(self) -> str:
        #    signed_str = 's' if self.signed else 'u'
        #    if self.precision == 0:
        #        return f"Number({signed_str}{self.length} {self.min_val}...{self.max_val})"
        #    else:
        #        return f"Number({signed_str}{self.length} {self.min_val}...{self.max_val} step {1/(1<<self.precision)})"
        #
        #def __repr__(self) -> str:
        #    return self.__str__()

        def get_rhs_slicer(self, key: Any, key_kind: KeyKind) -> 'Module':
            if key_kind != KeyKind.Index:
                raise SyntaxErrorException("Number only support array-style member access.")
            return Number.Accessor(key, self.get_net_type())

        @staticmethod
        def get_lhs_slicer(key_chains: Sequence[Sequence[Tuple[Any, KeyKind]]]) -> 'Module':
            return Number.Instance.PhiSlice(key_chains)
            
        class PhiSlice(GenericModule):
            """
            This class handles the case of member-wise assignment to Numbers. Things, like:

            a[3:0] <<= b
            a[3:0][1] <<= c

            and things like that.

            PhiSlices are type-specific and have different guts for ex. interfaces.

            For Numbers, they are collecting *all* the assignments to a given junction and generate
            a single assignment Verilog statement. This is needed because Verilog doesn't support
            multiple-assignment to (sections of) vectors.
            """
            output_port = Output()

            def construct(self, key_chains: Sequence[Sequence[Tuple[Any, KeyKind]]]):
                self.key_chains = key_chains
                self.input_map = None
            def create_positional_port_callback(self, idx: int) -> Optional[Union[str, Port]]:
                # Create the associated input to the key. We don't support named ports, only positional ones.
                if idx >= len(self.key_chains):
                    return None
                name = f"slice_{idx}"
                ret_val = Input()
                return (name, ret_val)

            def finalize_input_map(self, common_net_type: object):
                if self.input_map is not None:
                    return
                self.input_map = OrderedDict()
                keyed_inputs = set()
                for raw_key, input in zip(self.key_chains, self.get_inputs().values()):
                    remaining_keys, final_key = common_net_type.resolve_key_sequence_for_set(raw_key)
                    if remaining_keys is not None:
                        raise FixmeException("Can't resolve all keys in a LHS context. THIS COULD BE FIXED!!!!")
                    key = common_net_type.Key(final_key) # Convert the raw key into something that the common type understands
                    if key in self.input_map:
                        raise SyntaxErrorException(f"Input key {raw_key} is not unique for concatenator output type {common_net_type}")
                    self.input_map[key] = input
                    keyed_inputs.add(input)
                for input in self.get_inputs().values():
                    assert input in keyed_inputs, f"Strange: PhiSlice has an input {input} without an associated key"

            def generate_output_type(self) -> Optional['NumberMeta']:
                # This is one of the few cases where we do care about what port we're driving.
                # The reason for that is partial assignments, that are not allowed.
                # Let's say we have something, like this:
                #     w = Wire(Unsigned(8))
                #     w[0] = 1
                # This piece of code should not elaborate. However, if PhiSlice
                # auto-determines its output type, it'll think it's a 1-bit output.
                # Then auto-type-conversion simply zero-extends that to the rest of the bits.
                # Even if made that OK, the following would clearly be an error, 
                # confusing for the user even further:
                #     w = Wire(Unsigned(8))
                #     w[1] = 1
                # So, to remedy that, we'll look at the transitive closure of all sinks
                # of our output and use the smallest output range from them.
                # Why the smallest? Because if there are multiple sources,
                # those should participate in auto-extension. If it so happens
                # that our direct output is not the most restrictive, that would
                # mean that somewhere in the assignment chain, there was a narrowing,
                # which will eventually blow up.
                #
                # Precision auto-extends the other way: we need to make sure the least precise sink
                # is still good enough. It's always OK to append a bunch of 0-s to make the Number more 'precise'.
                common_net_type = get_common_net_type(self.get_inputs().values())
                if common_net_type is None:
                    raise SyntaxErrorException(f"Can't figure out output port type for PhiSlice {self}")
                if not is_number(common_net_type):
                    raise SyntaxErrorException(f"PhiSlice result type is {common_net_type}. It should be a Number")
                self.finalize_input_map(common_net_type)
                sinks = self.output_port.get_all_sinks()
                min_val = None
                max_val = None
                precision = None
                for sink in sinks:
                    if is_number(sink.get_net_type()):
                        min_val = max_none(min_val, sink.get_net_type().min_val)
                        max_val = min_none(max_val, sink.get_net_type().max_val)
                        precision = min_none(precision, sink.get_net_type().precision)
                if min_val is not None:
                    assert max_val is not None
                    assert precision is not None
                    output_type = Number(min_val=min_val, max_val=max_val, precision=precision)
                else:
                    output_type = common_net_type.concatenated_type(self.input_map)
                return output_type

            def body(self) -> None:
                new_net_type = self.generate_output_type()
                if new_net_type is None:
                    raise SyntaxErrorException(f"Can't figure out output port type for PhiSlice {self}")
                self.output_port.set_net_type(new_net_type)

            def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
                yield InlineExpression(self.output_port, *self.generate_inline_expression(back_end, target_namespace))
            def generate_inline_expression(self, back_end: 'BackEnd', target_namespace: Module) -> Tuple[str, int]:
                return self.output_port.get_net_type().compose_concatenated_expression(back_end, self.input_map, target_namespace)
            def simulate(self) -> TSimEvent:
                net_type = self.output_port.get_net_type()
                cache = net_type.prep_simulate_concatenated_expression(self.input_map)
                while True:
                    yield self.get_inputs().values()
                    self.output_port <<= net_type.simulate_concatenated_expression(cache)

            def is_combinational(self) -> bool:
                """
                Returns True if the module is purely combinational, False otherwise
                """
                return True






        @classmethod
        def get_lhs_name(cls, for_junction: Junction, back_end: 'BackEnd', target_namespace: Module, allow_implicit: bool=True) -> Optional[str]:
            assert back_end.language == "SystemVerilog"
            xnet = target_namespace._impl.netlist.get_xnet_for_junction(for_junction)
            name = xnet.get_lhs_name(target_namespace, allow_implicit=allow_implicit)
            if name is None:
                return None
            return name

        @classmethod
        def get_rhs_expression(cls, for_junction: Junction, back_end: 'BackEnd', target_namespace: Module, outer_precedence: Optional[int] = None, allow_expression: bool = True) -> Tuple[str, int]:
            xnet = target_namespace._impl.netlist.get_xnet_for_junction(for_junction)
            expr, prec = xnet.get_rhs_expression(target_namespace, back_end, allow_expression)
            if outer_precedence is not None and prec > outer_precedence:
                return f"({expr})", back_end.get_operator_precedence("()")
            else:
                return expr, prec

        @classmethod
        def generate_type_ref(cls, back_end: 'BackEnd') -> str:
            assert back_end.language == "SystemVerilog"
            if cls.signed:
                if cls.length > 1:
                    return f"logic signed [{cls.length - 1}:0]"
                else:
                    return f"logic signed"
            else:
                if cls.length > 1:
                    return f"logic [{cls.length - 1}:0]"
                else:
                    return f"logic"

        @classmethod
        def generate_net_type_ref(cls, for_junction: 'Junction', back_end: 'BackEnd') -> str:
            assert back_end.language == "SystemVerilog"
            return f"{for_junction.generate_junction_ref(back_end)} {cls.generate_type_ref(back_end)}"

        @classmethod
        def get_iterator(cls, parent_junction: Junction) -> Any:
            """
            Returns an iterator for the type (such as one that iterates through all the bits of a number)
            """
            return Number.Iterator(cls, parent_junction)
        @classmethod
        def get_length(cls) -> int:
            return cls.length

        @classmethod
        def get_slice(cls, key: Any, junction: Junction) -> Any:
            if Context.current() == Context.simulation:
                return Number.Accessor.static_sim(junction.sim_value, Number.Instance.Key(key), junction.get_net_type().precision)
            else:
                return Number.Accessor(slice=key, number=cls)(junction)

        @classmethod
        def set_member_access(cls, key: Any, value: Any, junction: Junction) -> None:
            # The junction conversion *has* to happen before the creation of the Concatenator.
            # Otherwise, the auto-created converter object (such as Constant) will be evaluated in the wrong order
            # and during the evaluation of the Concatenator, the inlined expression forwarding logic will break.
            from .utils import convert_to_junction
            real_junction = convert_to_junction(value, type_hint=None)
            junction.raw_input_map.append((key, real_junction))
        @classmethod
        def resolve_key_sequence_for_get(cls, keys: Sequence[Tuple[Any, KeyKind]], for_junction: Junction) -> Tuple[Optional[Sequence[Tuple[Any, KeyKind]]], Junction]:
            # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing
            # Returns the final junction and the remaining keys if they cannot be processed.
            # NOTE: for Numbers, this is easy, as the chain always produces more Numbers,
            #       so we should be able to fully process the chain. For other types, such
            #       as structs or interfaces, things get more complicated.
            # NOTE: Again, for Numbers only, set and get variants are nearly identical.
            remaining_keys, key = cls.resolve_key_sequence_for_set(keys)
            assert remaining_keys is None
            return remaining_keys, Number.Accessor(slice=key, number=for_junction.get_net_type())(for_junction)
        @classmethod
        def resolve_key_sequence_for_set(cls, keys: Sequence[Tuple[Any, KeyKind]]) -> Any:
            # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing for concatenators (set context)
            # Returns remaining keys (nothing for Numbers) and the resolved slice

            def _slice_of_slice(outer_key: Any, inner_key: Any) -> Any:
                # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing
                outer_key = Number.Instance.Key(outer_key)
                inner_key = Number.Instance.Key(inner_key)
                result_key = outer_key.apply(inner_key)
                if result_key.start == result_key.end:
                    return result_key.start
                else:
                    return slice(result_key.start, result_key.end, -1)

            key = keys[0]
            assert key[1] is KeyKind.Index, "Number doesn't support member access, only slices"
            key = key[0]
            for sub_key in keys[1:]:
                assert sub_key[1] is KeyKind.Index, "Number doesn't support member access, only slices"
                key = _slice_of_slice(key, sub_key[0])
            return None, key

        @classmethod
        def get_unconnected_sim_value(cls) -> Any:
            return None
        @classmethod
        def get_default_sim_value(cls) -> Any:
            return 0
        @classmethod
        def validate_sim_value(cls, sim_value: Any, parent_junction: Junction) -> Any:
            """
            Validates the new sim value before assignment.

            Raises exceptions with appropriate error messages in case of a validation error.

            Has the option to change/correct the sim_value prior to assignment.

            Returns potentially modified sim_value for assignment.
            """
            if sim_value is None:
                return sim_value
            if sim_value > cls.max_sim_val or sim_value < cls.min_sim_val:
                raise SimulationException(f"Can't assign to net '{parent_junction}' the value '{sim_value}'. That value is outside of the representable range.", parent_junction)
            return sim_value

        @classmethod
        def sim_constant_to_net_value(cls, value: 'Constant') -> 'Number.NetValue':
            if value.net_type is not cls:
                raise SimulationException(f"Can't assign a constant of type {value.net_type} to a net of type {cls}")
            return Number.NetValue(value.value, cls.precision)

        @classmethod
        def generate_const_val(cls, value: Optional[int], back_end: 'BackEnd') -> str:
            assert back_end.language == "SystemVerilog"
            length = cls.length
            if value is None:
                return f"{length}'bX"
            if value >= 0:
                return f"{length}'h{format(value, 'x')}"
            else:
                return f"-{length}'sh{format(-value, 'x')}"

        @classmethod
        def get_num_bits(cls) -> int:
            return cls.length

        @classmethod
        def convert_to_vcd_type(cls, value: Optional[int]) -> Any:
            """
            Converts the given native python value into the corresponding VCD-compatible value
            Must be overwritten for all sub-classes
            """
            if value is None:
                return 'X'
            if isinstance(value, Number.NetValue):
                return value.value
            assert False
            return value

        @classmethod
        def adapt_from(cls, input: Any, implicit: bool, force: bool) -> Any:
            context = Context.current()

            if context == Context.simulation:
                if input is None:
                    return None
                if is_junction_base(input):
                    input = input.sim_value
                elif isinstance(input, Number.NetValue):
                    pass
                else:
                    try:
                        input = Number.NetValue(int(input))
                    except TypeError:
                        raise SimulationException(f"Don't support input type f{type(input)}")

                int_input = int(input)
                if cls.min_val > int_input or cls.max_val < int_input:
                    if not force:
                        raise AdaptTypeError
                    else:
                        assert False, "FIXME: we should chop of top bits here!"
                        return adjust_precision_sim(input.value, input.precision, cls.precision)
                return input
            elif context == Context.elaboration:
                input_type = input.get_net_type()
                if not is_number(input_type):
                    raise AdaptTypeError
                if cls.min_val > input_type.min_val or cls.max_val < input_type.max_val:
                    if not force:
                        raise AdaptTypeError
                    else:
                        return Number.SizeAdaptor(input_type = input_type, output_type = cls)(input)
                if cls.length >= input_type.length and cls.signed == input_type.signed and cls.precision == input_type.precision:
                    return input
                output = Number.SizeAdaptor(input_type = input_type, output_type = cls)(input)
                #output.get_parent_module()._impl._elaborate(hier_level=0, trace=False)
                return output

        @classmethod
        def result_type(cls, net_types: Sequence[Optional['NetType']], operation: str) -> 'NetType':
            """
            Returns the NetType that can describe any possible result of the specified operation,
            given the paramerters to said operation are (in order) are of the specified types.

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
                NOT
                NEG
                ABS
            """
            def check_all_types_valid():
                if any(net_type is None for net_type in net_types):
                    raise SyntaxErrorException("Can't determine union type unless all input types are specified")

            assert len(net_types) > 0
            for net_type in net_types:
                if net_type is not None and not issubclass(net_type, Number.Instance):
                    raise SyntaxErrorException("Can only determine union type if all constituents are Numbers")
            if operation == "SELECT":
                max_val = None
                min_val = None
                precision = None
                for net_type in net_types:
                    if net_type is None:
                        continue
                    max_val = max_none(max_val, net_type.max_val)
                    min_val = min_none(min_val, net_type.min_val)
                    precision = max_none(precision, net_type.precision)
                return Number(max_val=max_val, min_val=min_val, precision=precision)
            elif operation in ("OR", "AND", "XOR"):
                all_signed = True
                all_unsigned = True
                final_signed = False
                max_len = 0
                max_unsigned_len = 0
                precision = net_types[0].precision
                for net_type in net_types:
                    if net_type is None:
                        continue
                    max_len = max(max_len, net_type.length)
                    if net_type.signed:
                        all_unsigned = False
                        final_signed = True
                    else:
                        all_signed = False
                        max_unsigned_len = max(max_unsigned_len, net_type.length)
                    if net_type.precision != precision:
                        raise SyntaxErrorException("Can't determine union type unless all constituents have the same precision")
                assert not all_signed or not all_unsigned
                if not all_signed and not all_unsigned:
                    # FIXME: If some ports are signed and some are unsigned, we might have to sign-extend the result by an extra bit
                    #        in case the longest input was unsigned. However I'm not sure that's what we want to do. For now, leave it as-is
                    #max_len = max(max_len, max_unsigned_len + 1)
                    pass
                ret_val = Number(length=max_len, signed=final_signed, precision=precision)
                #print(f"------ returning {ret_val} for inputs: " + ",".join(str(net_type) for net_type in net_types))
                return ret_val
            elif operation == "SUM":
                max_val = 0
                min_val = 0
                for net_type in net_types:
                    if net_type is None:
                        continue
                    max_val = max_val + net_type.max_val
                    min_val = min_val + net_type.min_val
                return Number(max_val=max_val, min_val=min_val, precision=max(n.precision for n in net_types))
            elif operation == "SUB":
                assert len(net_types) == 2
                check_all_types_valid()
                max_val = net_types[0].max_val - net_types[1].min_val
                min_val = net_types[0].min_val - net_types[1].max_val
                return Number(max_val=max_val, min_val=min_val, precision=max(n.precision for n in net_types))
            elif operation == "PROD":
                max_val = 1
                min_val = 1
                for net_type in net_types:
                    if net_type is None:
                        continue
                    max_val = max(
                        max_val * net_type.max_val,
                        max_val * net_type.min_val,
                        min_val * net_type.max_val,
                        min_val * net_type.min_val
                    )
                    min_val = min(
                        max_val * net_type.max_val,
                        max_val * net_type.min_val,
                        min_val * net_type.max_val,
                        min_val * net_type.min_val
                    )
                return Number(max_val=max_val, min_val=min_val, precision=prod(n.precision for n in net_types))
            elif operation == "SHL":
                assert len(net_types) == 2
                check_all_types_valid()
                if net_types[1].precision != 0:
                    raise SyntaxErrorException("Shift amount must be integer")

                if net_types[0].min_val > 0:
                    min_val = net_types[0].min_val << net_types[1].min_val
                else:
                    min_val = net_types[0].min_val << net_types[1].max_val

                if net_types[0].max_val > 0:
                    max_val = net_types[0].max_val << net_types[1].max_val
                else:
                    max_val = net_types[0].max_val << net_types[1].min_val

                precision = max(net_types[0].precision - net_types[1].min_val, 0)

                return Number(max_val=max_val, min_val=min_val, precision=precision)
            elif operation == "SHR":
                assert len(net_types) == 2
                check_all_types_valid()
                if net_types[1].precision != 0:
                    raise SyntaxErrorException("Shift amount must be integer")

                if net_types[0].min_val > 0:
                    min_val = net_types[0].min_val >> net_types[1].max_val
                else:
                    min_val = net_types[0].min_val >> net_types[1].min_val

                if net_types[0].max_val > 0:
                    max_val = net_types[0].max_val >> net_types[1].min_val
                else:
                    max_val = net_types[0].max_val >> net_types[1].max_val

                #precision = max(net_types[0].precision + net_types[1].max_val, 0)
                # This is a bit asymmetrical, but the idea is that right-shift always truncates the bits it shifts out, even for fractional types.
                precision = net_types[0].precision

                return Number(max_val=max_val, min_val=min_val, precision=precision)
            elif operation == "NOT":
                assert len(net_types) == 1
                check_all_types_valid()
                # NOTE: it feels as if this is the same type, but it's not: it's the full binary range of the input, where as min/max for the input could be something smaller
                return Number(length=net_types[0].length, signed=net_types[0].signed, precision=net_types[0].precision)
            elif operation == "NEG":
                assert len(net_types) == 1
                check_all_types_valid()
                return Number(min_val=-net_types[0].max_val, max_val=-net_types[0].min_val, precision=net_types[0].precision)
            elif operation == "ABS":
                assert len(net_types) == 1
                check_all_types_valid()
                if net_types[0].min_val < 0 and net_types[0].max_val > 0:
                    min_val = 0
                else:
                    min_val = min(abs(net_types[0].min_val), abs(net_types[0].max_val))
                max_val = max(abs(net_types[0].min_val), abs(net_types[0].max_val))
                return Number(min_val=min_val, max_val=max_val, precision=net_types[0].precision)
            else:
                return super().result_type(net_types, operation) # Will raise an exception.

        """
        ============================================================================================
        Concatenator support
        ============================================================================================
        """
        @classmethod
        def _overlap(cls, range1 : 'Number.Instance.Key', range2: 'Number.Instance.Key') -> bool:
            # Local method, not called from outside
            assert not range1.is_sequential and not range2.is_sequential
            assert range1.start >= range1.end
            assert range2.start >= range2.end
            if range1.end > range2.start:
                return False
            if range2.end > range1.start:
                return False
            return True
        @classmethod
        def validate_input_map(cls, input_map: Dict['Number.Instance.Key', Junction]) -> bool:
            """
            Returns True if the supplied input map is valid, False otherwise

            input_map can contain:
            - One more more inputs with a sequential key. In that case, the inputs are simply concatenated
            (in MSB->LSB order) in the order they were inserted into the map. This is the SV {a,b,c}
            concatenation behavior.
            - One more more inputs with a slice or integer-based keys. In that case the inputs are assigned
            (potentially sign- or zero-extended) to the range specified by the key.
            - The map must contain at least one input.
            It is invalid to have both None-keyed and range-keyed elements in the map.
            """
            # Local method, not called from outside
            if len(input_map) == 0:
                return False
            found_seq= False
            all_seq= True
            for key in input_map.keys():
                if not key.is_sequential:
                    all_seq = False
                else:
                    found_seq = True
                if not all_seq and found_seq:
                    return False
            if all_seq:
                return True
            assert not found_seq
            from itertools import combinations
            for (range1, range2) in combinations(input_map.keys(), 2):
                if cls._overlap(range1, range2):
                    return False
            return True
        @classmethod
        def is_sequential_map(cls, input_map: Dict['Number.Instance.Key', Junction]) -> bool:
            """
            Returns true if the provided input_map is all sequential

            input_map can contain:
            - One more more inputs with a sequential key. In that case, the inputs are simply concatenated
            (in MSB->LSB order) in the order they were inserted into the map. This is the SV {a,b,c}
            concatenation behavior.
            - One more more inputs with a slice or integer-based keys. In that case the inputs are assigned
            (potentially sign- or zero-extended) to the range specified by the key.
            - The map must contain at least one input.
            It is invalid to have both None-keyed and range-keyed elements in the map.
            """
            # Local method, not called from outside
            assert len(input_map) > 0
            for key in input_map.keys():
                if not key.is_sequential:
                    return False
            return True
        @classmethod
        def sort_source_keys(cls, input_map: Dict['Number.Instance.Key', Junction], back_end: Optional['BackEnd']) -> Tuple['Number.Instance.Key']:
            """
            Sort the set of blobs as required by the back-end or for simulation if back_end is None
            """
            # Local method, not called from outside
            assert back_end is None or back_end.language == "SystemVerilog"
            from operator import attrgetter
            if len(input_map) == 1 or cls.is_sequential_map(input_map):
                return tuple(input_map.keys())
            sorted_keys = tuple(sorted(input_map.keys(), key=attrgetter('start'), reverse=True))
            return sorted_keys

        @classmethod
        def concatenated_type(cls, input_map: Dict['Number.Instance.Key', Junction]) -> Optional['NetType']:
            """
            Returns the combined type for the given inputs for the keys

            The combined type is always an integer: there's not fractional part to a concatenation.
            """
            assert len(input_map) > 0
            if not cls.validate_input_map(input_map):
                raise SyntaxErrorException("Can only determine concatenated type if the input map is invalid")
            for junction in input_map.values():
                if not is_number(junction.get_net_type()):
                    raise SyntaxErrorException("Can only determine concatenated type if all constituents are Numbers")
            # Simple assignment: return the input, but converted into an integer
            if len(input_map) == 1 and first(input_map.keys()).is_sequential:
                input_type = first(input_map.values()).get_net_type()
                return Number(length=input_type.length, signed=input_type.signed)
            # Either multiple sources or the single source has a range assigned to it.
            sorted_keys = cls.sort_source_keys(input_map, back_end = None)
            top_key = first(sorted_keys)
            signed=input_map[top_key].signed # The top-most entry determines the signed-ness of the result
            if not top_key.is_sequential:
                # If the top entry is not sequential, then none of them are: the length of the result is determined by the top position of the top entry
                return Number(length=top_key.start+1, signed=signed)
            # If all entries are sequential, we simply need to add up the lengths of the constituents
            length = 0
            for input in input_map.values():
                length += input.length
            return Number(length=length, signed=signed)

        @classmethod
        def compose_concatenated_expression(cls, back_end: 'BackEnd', input_map: Dict['Number.Instance.Key', Junction], target_namespace: Module) -> Tuple[str, int]:
            def compose_sub_source_expression(sub_port: Junction, section_length: int) -> Tuple[str, int]:
                raw_expr, precedence = sub_port.get_rhs_expression(back_end, target_namespace)
                if sub_port.get_net_type().length == section_length or section_length == cls.length:
                    # If the request source is of the right length or it covers the whole junction, return it as-is
                    return raw_expr, precedence
                elif sub_port.get_net_type().length > section_length:
                    raise SyntaxErrorException("Can't assign section of a Number form another, longer Number")
                    # Well, in fact we could, but do we want to? That's too close to a coding error to allow it...
                    #return f"({raw_expr})[section_length-1:0]"
                else:
                    return f"{section_length}'({raw_expr})", 0

            # No source: return a X-assignment
            assert back_end.language == "SystemVerilog"
            if len(input_map) == 0:
                return f"{cls.length}'bX", 0

            sorted_keys = cls.sort_source_keys(input_map, back_end)
            last_top_idx = cls.length
            rtl_parts = []
            for sub_port_key in sorted_keys:
                current_top_idx = sub_port_key.start if not sub_port_key.is_sequential else last_top_idx - 1
                assert current_top_idx < last_top_idx
                if current_top_idx < last_top_idx - 1:
                    raise SyntaxErrorException("Not all bits in Number have sources")
                sub_port = input_map[sub_port_key]
                last_top_idx = sub_port_key.end if not sub_port_key.is_sequential else last_top_idx - sub_port.length
                slice_length = sub_port_key.length if not sub_port_key.is_sequential else sub_port.length
                rtl_parts.append(compose_sub_source_expression(sub_port, slice_length))
            if last_top_idx > 0:
                raise SyntaxErrorException("Not all bits in Number have sources")
            if len(rtl_parts) == 1:
                return rtl_parts[0]
            # For now we're assuming that concatenation returns an UNSIGNED vector independent of the SIGNED-ness of the sources.
            # This is indeed true according to https://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.449.1578&rep=rep1&type=pdf
            ret_val = "{" + ", ".join(rtl_part[0] for rtl_part in rtl_parts) + "}"
            if cls.signed:
                return back_end.signed_cast(ret_val), 0
            else:
                return ret_val, back_end.get_operator_precedence("{}")

        @classmethod
        def prep_simulate_concatenated_expression(cls, input_map: Dict['Number.Instance.Key', Junction]) -> Any:
            """
            Returns whatever cached values are needed for quick simulation of concatenation.
            This cached value is stored in the caller (Concatenator) object and is passed in to
            simulate_concatenated_expression below.
            """
            concat_map = []
            sorted_keys = cls.sort_source_keys(input_map, None)
            last_top_idx = cls.length
            value = 0
            for sub_port_key in sorted_keys:
                current_top_idx = sub_port_key.start + cls.precision if not sub_port_key.is_sequential else last_top_idx - 1
                assert current_top_idx < last_top_idx
                if current_top_idx < last_top_idx - 1:
                    raise SyntaxErrorException("Not all bits in Number have sources")
                sub_port = input_map[sub_port_key]
                last_top_idx = sub_port_key.end + cls.precision if not sub_port_key.is_sequential else last_top_idx - sub_port.length
                concat_map.append((sub_port, last_top_idx))
            return concat_map

        @classmethod
        def simulate_concatenated_expression(cls, prep_cache: Any) -> int:
            value = 0
            for sub_port, last_top_idx in prep_cache:
                sub_source_value = sub_port.sim_value
                if sub_source_value is None:
                    return None
                value |= sub_source_value << last_top_idx
            return value


    net_type = Instance













def int_to_const(value: int, type_hint: Optional[NetType]) -> Tuple[NetType, int]:
    return Number(min_val=value, max_val=value), value

def _str_to_int(value: str) -> Tuple[int, int, bool]:
    """
    Since we don't have custom literals in Python, we'll have to roll our
    custom strings so that we can represent constants of a certain size.

    This is to be able to quickly represent the notion of 4'b0 from Verilog,
    which is very important for quick concatenations, such as [a1, 4'b0, a2].

    The notation used here is identical to Verilogs literals:

    [-]<bit width>'[b|o|h|d]<digits>

    What's not supported:
    - missing bit width field.
    """
    negative = False
    if value[0] == '-':
        negative = True
        value = value[1:]
    elif value[0] == '+':
        value = value[1:]
    size_delim = value.find("'")
    if size_delim == -1 or size_delim == 0:
        raise SyntaxErrorException(f"String '{value}' isn't a valid Constant. It misses the ' size delimiter")
    size_field = value[0:size_delim]
    value_field = value[size_delim+1:]
    base_field = value_field[0]
    base_convert = {"d": 10, "D": 10, "h": 16, "H": 16, "o": 8, "O": 8, "b": 2, "B": 2, "x": 16, "X": 16}
    if base_field not in base_convert:
        raise SyntaxErrorException(f"String '{value}' isn't a valid Constant. It's base '{base_field}' is not valid.")
    base = base_convert[base_field]
    try:
        size = int(size_field)
    except ValueError:
        raise SyntaxErrorException(f"String '{value}' isn't a valid Constant. It's size field '{size_field}' isn't an integer")
    try:
        int_value = int(value_field[1:], base)
    except ValueError:
        raise SyntaxErrorException(f"String '{value}' isn't a valid Constant. It's value field '{value_field}' isn't an integer")
    if negative:
        int_value = -int_value

    if negative:
        max_val = 2 ** (size - 1) - 1
        min_val = -(2 ** (size - 1))
        if int_value > max_val or int_value < min_val:
            raise SyntaxErrorException(f"String '{value}' isn't a valid Constant. It's value field '{value_field}' doesn't fit in the declared size")
    else:
        if int_value > 2 ** size - 1:
            raise SyntaxErrorException(f"String '{value}' isn't a valid Constant. It's value field '{value_field}' doesn't fit in the declared size")
    return (int_value, size, negative)

def str_to_const(value: str, type_hint: Optional[NetType]) -> Tuple[NetType, int]:
    int_val, size, negative = _str_to_int(value)
    net_type = Number(length=size, signed=negative)
    assert int_val >= net_type.min_val and int_val <= net_type.max_val
    return net_type, int_val

def float_to_const(value: float, type_hint: Optional[NetType]) -> int:
    # We are converting a float to the (nearest) representable fixed-point value
    if not is_number(type_hint):
        raise SimulationException(f"Can only assign a floating point value to a Number")
    value_as_int = round(value * (2 ** type_hint.precision))
    #return type_hint, Number.NetValue(value_as_int, type_hint.precision)
    return type_hint, value_as_int

def bool_to_const(value: bool, type_hint: Optional[NetType]) -> Tuple[NetType, int]:
    if value:
        return Unsigned(1), 1
    else:
        return Unsigned(1), 0

from .constant import const_convert_lookup

const_convert_lookup[int] = int_to_const
const_convert_lookup[str] = str_to_const
const_convert_lookup[bool] = bool_to_const
const_convert_lookup[float] = float_to_const

def Signed(length: int=None) -> NumberMeta:
    return Number(length=length, signed=True)

def Unsigned(length: int=None) -> NumberMeta:
    return Number(length=length, signed=False)

logic = Number(length=1, signed=False)
ulogic = logic
slogic = Number(length=1, signed=True)

