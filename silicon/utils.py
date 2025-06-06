from typing import Union, Sequence, Any, Optional, Iterable, Dict, List, Callable, IO, Sequence, Tuple, Generator, Set, Iterator
from .exceptions import SyntaxErrorException, AdaptTypeError
from threading import RLock
import sys

TSimEvent = Generator[Union[int, Sequence['Port']], int, int]

# Only purpose to provide an easy way to check if something is a NetValue in convert_to_junction
class NetValue(object):
    pass
class Context(object):
    stack = []
    listeners = set()

    @staticmethod
    def register(callback: Callable):
        Context.listeners.add(callback)
        callback(Context.current())
    @staticmethod
    def unregister(callback: Callable):
        Context.listeners.remove(callback)

    @staticmethod
    def push(context: Any):
        notify = context != Context.current()
        Context.stack.append(context)
        if notify:
            for callback in Context.listeners:
                callback(context)

    @staticmethod
    def pop() -> Any:
        ret_val = Context.stack.pop()
        new_context = Context.current()
        if ret_val != new_context:
            for callback in Context.listeners:
                callback(new_context)
        return ret_val

    @staticmethod
    def current() -> Any:
        if len(Context.stack) == 0:
            return None
        return Context.stack[-1]

    construction = 1
    elaboration = 2
    simulation = 3
    generation = 4

class ContextMarker(object):
    def __init__(self, context: Any):
        self.context = context
    def __enter__(self):
        Context.push(self.context)
        return self
    def __exit__(self, type, value, traceback):
        old_context = Context.pop()
        assert old_context == self.context



def is_iterable(thing: Any) -> bool:
    try:
        _ = iter(thing)
    except TypeError:
        return False
    else:
        return True

def is_subscriptable(thing: Any) -> bool:
    return hasattr(thing, "__getitem__")

def is_junction(thing: Any) -> bool:
    #return hasattr(thing, "junction_kind")
    from .port import Junction
    return isinstance(thing, Junction)

def is_output_port(thing: Any) -> bool:
    return hasattr(thing, "junction_kind") and thing.junction_kind == "output"

def is_input_port(thing: Any) -> bool:
    return hasattr(thing, "junction_kind") and thing.junction_kind == "input"

def is_wire(thing: Any) -> bool:
    return hasattr(thing, "junction_kind") and thing.junction_kind == "wire"

def is_module(thing: Any) -> bool:
    from .module import Module
    return isinstance(thing, Module)

def is_net_type(thing: Any) -> bool:
    from .net_type import NetType, NetTypeMeta
    if not isinstance(thing, NetTypeMeta):
        return False
    try:
        return issubclass(thing, NetType)
    except TypeError:
        return False

def is_net_value(thing: Any) -> bool:
    return isinstance(thing, NetValue)

def convert_to_junction(thing: Any, type_hint: Optional['NetType']=None) -> Optional['Junction']:
    """
    Convert the input 'thing' into a port, if possible. Returns None if such conversion is not possible
    """
    from .constant import ConstantModule, _const
    from .primitives import Concatenator
    import collections

    if is_junction(thing):
        return thing
    context = Context.current()
    if context == Context.elaboration:
        if hasattr(thing, "convert_to_junction"):
            thing = thing.convert_to_junction(type_hint)
        if hasattr(thing, "get_underlying_junction"):
            return thing.get_underlying_junction()
    elif context == Context.simulation:
        if thing is None:
            return None
        if hasattr(thing, "sim_value"):
            return thing.sim_value
        if is_net_value(thing):
            return thing
    else:
        assert False, f"Unknown context: '{context}'"

    const_val = _const(thing, type_hint)

    if const_val is not None:
        if context == Context.elaboration:
            return ConstantModule(const_val)()
        elif context == Context.simulation:
            return const_val.net_type.sim_constant_to_net_value(const_val)

    # _const failed to find us what we were looking for.
    # There can be two reasons for it: either it's a string that didn't convert, or some other, unknown type.
    # We will check for the first, then try a few implicit conversions to get to our goal.
    if isinstance(thing, str):
        raise SyntaxErrorException(f"Can't convert '{thing}' into a constant")
    if hasattr(thing, "__bool__"):
        # Use bool-conversion to get to the value
        # NOTE: pretty much anything converts to a bool, so simply trying and catching the TypeError is not an option here
        return convert_to_junction(bool(thing), type_hint)
    try:
        return convert_to_junction(int(thing), type_hint)
    except TypeError:
        pass
    try:
        # NOTE: pretty much anything converts to a str, so this must be the last resort
        return convert_to_junction(str(thing), type_hint)
    except TypeError:
        return None

FQN_DELIMITER = "."

MEMBER_DELIMITER="_"

def first(collection: Iterable[Any]) -> Any:
    return next(iter(collection))

class StreamBlock(object):
    def __init__(self, base_stream: IO, header: str, footer: str):
        self.base_stream = base_stream
        self.header = header
        self.footer = footer
        self.has_output = False
    def __enter__(self):
        self.has_output = False
        return self
    def __exit__(self, type, value, traceback):
        if self.has_output:
            print(self.footer, file=self.base_stream)
        return False
    def write(self, data: str):
        if not self.has_output:
            self.has_output = True
            print(self.header, file=self.base_stream)
        self.base_stream.write(data)
    def flush(self):
        self.base_stream.flush()
    @property
    def encoding(self) -> str:
        return self.base_stream.encoding

def str_block(block: Optional[str], header: str, footer: str):
    if block is not None and len(block) > 0:
        return header + block + footer
    else:
        return ""


def implicit_adapt(input: Any, output_type: 'NetType') -> Union['Junction', Dict['str', 'Junction']]:
    """
    Implicitly adapts input to output_type.

    Implicit adaption happens when mismatched port-types are bound together.

    If 'force' is set to True, an adaptor is inserted even if input is already of the right type

    The return value is either a single port or a set of ports, for member-wise adaption.
    This later one is for Composites and it's the responsibility of the 'adapt_from' or
    'adapt_to' to decide which of the two methods are used.
    """
    return adapt(input, output_type, implicit=True, force=False, allow_memberwise_adapt=True)


def explicit_adapt(input: Any, output_type: 'NetType') -> 'Junction':
    """
    Explicitly adapts input to output_type. If adaption would require force, it raises an exception.

    NOTE: forcing an adaption means for instance to change a Number from a wider to a narrower range.

    The return value is either a single port or a set of ports, for member-wise adaption.
    This later one is for Composites and it's the responsibility of the 'adapt_from' or
    'adapt_to' to decide which of the two methods are used.
    """
    return adapt(input, output_type, implicit=False, force=False, allow_memberwise_adapt=False)


def cast(input: Any, output_type: 'NetType') -> 'Junction':
    """
    Casts input to output_type. Forces adaption, on top of being explicit.

    NOTE: forcing an adaption means for instance to change a Number from a wider to a narrower range.
    """
    return adapt(input, output_type, implicit=False, force=True, allow_memberwise_adapt=False)

def adapt(input: Any, output_type: 'NetType', implicit: bool, force: bool, allow_memberwise_adapt: bool) -> Union['Junction', Dict['str', 'Junction']]:
    """
    Creates an adaptor instance if needed to convert input to output_type.
    Returns the generated output port. If such adaptation is not possible, raises an exception

    If the type of the input is not know, a delayed adaptor is created.

    The return value is either a single port or a set of ports, for member-wise adaption.
    This later one is for Composites and it's the responsibility of the 'adapt_from' or
    'adapt_to' to decide which of the two methods are used.
    """
    try:
        if output_type is input.get_net_type():
            return input
    except AttributeError:
        pass

    try:
        if not input.is_specialized():
            from .module import GenericModule, InlineExpression
            from .port import Input, Output

            class DelayedAdaptor(GenericModule):
                """
                Allows for adaption of types that are unknown at the time of the call for adopt
                """
                input_port = Input()
                output_port = Output()

                def construct(self, output_type, implicit: bool, force: bool):
                    self.implicit = implicit
                    self.force = force
                    self.output_port.set_net_type(output_type)
                    self.is_trivial = False
                def body(self):
                    adapted = adapt(self.input_port, self.output_port.get_net_type(), self.implicit, self.force, allow_memberwise_adapt=False)
                    self.is_trivial = adapted is self.input_port
                    self.adaptor = adapted.get_parent_module()
                    self.output_port <<= adapted
                def get_inline_block(self, back_end: 'BackEnd', target_namespace: 'Module') -> Generator['InlineBlock', None, None]:
                    # Delegate inlining (if possible) to the adapter
                    if self.is_trivial:
                        yield InlineExpression(
                            self.output_port,
                            *self.input_port.get_rhs_expression(back_end, target_namespace, self.output_port.get_net_type())
                        )
                    else:
                        yield from self.adaptor.get_inline_block(back_end, target_namespace)
                def is_combinational(self) -> bool:
                    return True
            return DelayedAdaptor(output_type, implicit, force)(input)
    except AttributeError:
        pass

    input = convert_to_junction(input, output_type)
    try:
        return output_type.adapt_from(input, implicit, force, allow_memberwise_adapt)
    except AdaptTypeError:
        try:
            return input.get_net_type().adapt_to(output_type, input, implicit, force, allow_memberwise_adapt)
        except AdaptTypeError:
            raise SyntaxErrorException(f"Can't generate adaptor from {input.get_net_type().__name__} to {output_type.__name__} for port {input}")
        except AttributeError:
            raise SyntaxErrorException(f"Can't generate adaptor from {input} to {output_type}")

def common_superclass(*args, **kwargs) -> object:
    """
    Returns the most specialized common superclass of all supplied arguments
    """
    all_args = list(args) + list(kwargs.values())
    assert len(all_args) > 0

    from inspect import getmro
    candidates = list(getmro(all_args[0]))
    for arg in all_args[1:]:
        bases = set(getmro(arg))
        candidates = [candidate for candidate in candidates if candidate in bases]
        if len(candidates) == 1:
            assert candidates[0] is object
            return candidates[0]
    assert candidates[0] is not object
    return candidates[0]

def get_common_net_type(junctions: Sequence['Junction'], partial_results: bool = False) -> Optional[object]:
    from .constant import NoneNetType

    # All inputs are None, our output is None as well (this is a case where all inputs are explicitly unconnected)
    if all(junction.get_net_type is NoneNetType for junction in junctions):
        return NoneNetType
    # Only consider the connected inputs: None is just X, which can be of any type
    net_types = tuple(junction.get_net_type() for junction in junctions if junction.get_net_type() is not NoneNetType)
    # If any ports have unassigned type, we can't determine the common type.
    if any(net_type is None for net_type in net_types):
        return None
    if len(net_types) == 0:
        return None
    superclass = common_superclass(*net_types)
    from .net_type import NetType, NetTypeMeta
    from inspect import getmro
    with ScopedAttr(NetTypeMeta, "eq_is_is", True):
        if superclass in (object, NetType) or NetType not in getmro(superclass):
            junction_list_as_str = " ".join(str(junction) for junction in junctions)
            raise SyntaxErrorException(f"Ports {junction_list_as_str} don't have a common superclass.")
    return superclass

def get_caller_local_junctions(frame_cnt: int = 1) -> Dict[str, 'Junction']:
    import inspect as inspect
    from .port import is_junction_base
    caller_frame = inspect.currentframe()
    while frame_cnt > 0:
        caller_frame = caller_frame.f_back
        frame_cnt-=1
    caller_local_junctions = {}
    for name, value in caller_frame.f_locals.items():
        if is_junction_base(value):
            caller_local_junctions[name] = value
    del value
    del caller_frame
    return caller_local_junctions

def fill_arg_names(function: Callable, args: List[Any], kwargs: Dict[str, Any]) -> Tuple:
    """
    Makes best attempt at assigning argument names to args as it applies to an invocation of function.
    Returns modified args and kwargs list
    """

    my_args = list(args)
    my_kwargs = kwargs

    # mock-bind the now created invocation arguments to the signature of the function
    # and attempt to locate the ports that need a name. This might fail if 'function' itself
    # has *args or **kwargs arguments
    from inspect import signature
    sig = signature(function)
    bound_args = sig.bind(*my_args, **my_kwargs).arguments
    for name, arg in bound_args.items():
        if arg in my_args:
            my_kwargs[name] = arg
            my_args.remove(arg)

    return (tuple(my_args), my_kwargs)

def is_power_of_two(n: int) -> bool:
    return (n & (n-1) == 0) and n != 0

def get_composite_member_name(names: Sequence[str], delimiter: str = ".") -> str:
    return delimiter.join(names)

def min_none(*args):
    return min(a for a in args if a is not None)

def max_none(*args):
    return max(a for a in args if a is not None)

def adjust_precision(input: 'Junction', expression: str, precedence: int, target_precision: int, back_end: 'BackEnd') -> Tuple[str, int]:
    assert back_end.language == "SystemVerilog"

    ret_val = expression
    if input.precision != target_precision:
        # We need to either truncate some bits at the end or append some 0-s to make sure the precision field is of the right size
        # We will do that using logic operator instead of slicing, because slicing doesn't work on expressions within Verilog and
        # we *really* don't want to create another Verilog wire this deep down in expression generation
        if input.precision > target_precision:
            # Need to cut some bits off --> shift left
            if input.signed:
                op = ">>>"
            else:
                op = ">>"
            ret_val, precedence = back_end.wrap_expression(ret_val, precedence, back_end.get_operator_precedence(op))
            ret_val = f"{ret_val} {op} {input.precision - target_precision}"
        else:
            # Need to add some bits --> concatenate
            ret_val, precedence = back_end.wrap_expression(ret_val, precedence, back_end.get_operator_precedence("{}"))
            ret_val = f"{{ {ret_val}, {target_precision - input.precision}'b0 }}"
    return ret_val, precedence

def adjust_precision_sim(input_value: Optional[int], input_precision: int, target_precision: int) -> int:
    if input_value is None:
        return None
    shift = input_precision - target_precision
    if shift > 0:
        return input_value >> shift
    elif shift < 0:
        return input_value << -shift
    else:
        return input_value

def first_bit_set(x):
    """
    Returns the index, counting from 0, of the
    least significant set bit in `x`.
    """
    return (x&-x).bit_length()-1

class VerbosityLevels(object):
    none=-1
    instantiation=0

    _verbosity_level: int = -1

def set_verbosity_level(verbosity_level: int) -> None:
    VerbosityLevels._verbosity_level = verbosity_level

def verbose_enough(verbosity_level: int) -> bool:
    return get_verbosity_level() >= verbosity_level


def get_verbosity_level() -> int:
    return VerbosityLevels._verbosity_level

def vprint(verbosity_level: int, *args, **kwargs):
    """
    Same as 'print', except it is printing only at certain verbosity levels, and always targets STDERR
    """
    if verbose_enough(verbosity_level):
        print(*args, **kwargs, file=sys.stderr)


class ScopedAttr(object):
    """
    A small object that allows the setting of an attribute of an object for the scope of a with block
    """
    def __init__(self, obj: Any, attr: str, value: Any):
        self.obj = obj
        self.attr = attr
        self.value = value
    def __enter__(self) -> 'ScopedAttr':
        if hasattr(self.obj, self.attr):
            self.old_value = getattr(self.obj, self.attr)
        setattr(self.obj, self.attr, self.value)
        return self
    def __exit__(self, exception_type, exception_value, traceback):
        if hasattr(self, "old_value"):
            setattr(self.obj, self.attr, self.old_value)
        else:
            delattr(self.obj, self.attr)
        del self.old_value

def no_rtl(junction: 'JunctionBase') -> 'JunctionBase':
    from .port import is_junction_base
    if not is_junction_base(junction):
        raise SyntaxErrorException(f"no_rtl can only be set on a junction")
    junction._no_rtl = True
    return junction

def raise_for_caller(exception: Exception):
    try:
        raise exception
    except Exception as ex:
        import sys
        import traceback
        import types
        traceback = sys.exc_info()[2]
        back_frame = traceback.tb_frame.f_back.f_back
        back_tb = types.TracebackType(
            tb_next=None,
            tb_frame=back_frame,
            tb_lasti=back_frame.f_lasti,
            tb_lineno=back_frame.f_lineno
        )
        raise ex.with_traceback(back_tb)

support_profile = False
def profile(func):
    def wrapper(*args, **kwargs):
        def _finalize_profile(profiler, file_name):
            import pstats as pstats
            import io as io
            nonlocal old_profiler

            try:
                profiler.disable()
            except AttributeError:
                import sys
                sys.setprofile(old_profiler)
            s = io.StringIO()
            sortby = 'cumulative'
            ps = pstats.Stats(profiler, stream=s).sort_stats(sortby)
            #ps.print_stats()
            ps.dump_stats(file_name)
            #print(s.getvalue())

        import cProfile as profile
        pr = profile.Profile()
        try:
            pr.enable()
        except AttributeError:
            import sys
            old_profiler = sys.getprofile()
            sys.setprofile(pr.dispatcher)
        try:
            return func(*args, **kwargs)
        finally:
            _finalize_profile(pr,f"{func.__name__}.profile.out")
            pass
    if support_profile:
        return wrapper
    return func

def increment(wire):
    net_type = wire.get_net_type()
    return net_type(wire+1)

def decrement(wire):
    net_type = wire.get_net_type()
    return net_type(wire-1)

