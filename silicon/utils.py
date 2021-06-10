from typing import Union, Sequence, Any, Optional, Iterable, Dict, List, Callable, IO, Sequence, Tuple, Generator, Set, Iterator

from .tracer import no_trace
from .exceptions import SyntaxErrorException
from collections import deque
from threading import RLock

TSimEvent = Generator[Union[int, Sequence['Port']], int, int]

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
    from .port import JunctionBase
    return isinstance(thing, JunctionBase)

def is_port(thing: Any) -> bool:
    from .port import Port
    return isinstance(thing, Port)

def is_junction_member(thing: Any) -> bool:
    from .member_access import MemberGetter
    return isinstance(thing, MemberGetter)

def is_junction_or_member(thing: Any) -> bool:
    return is_junction_member(thing) or is_junction(thing)

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
    from .net_type import NetType
    return isinstance(thing, NetType)


def convert_to_junction(thing: Any) -> Optional['Junction']:
    """
    Convert the input 'thing' into a port, if possible. Returns None if such conversion is not possible
    """
    from .constant import ConstantModule, _const
    from .primitives import Concatenator
    import collections
    
    if hasattr(thing, "get_underlying_junction"):
        return thing.get_underlying_junction()
    const_val = _const(thing)
    if const_val is not None:
        return ConstantModule(const_val)()
    elif isinstance(thing, collections.abc.Mapping):
        assert False, "FIXME: this is where direct struct assignment would go"
    elif isinstance(thing, str):
        raise SyntaxErrorException(f"Can't convert string '{thing}' into a constant")
    elif is_iterable(thing):
        return Concatenator(*thing)
    elif hasattr(thing, "__bool__") or hasattr(thing, "__len__"):
        # Use bool-conversion to get to the value
        return convert_to_junction(bool(thing))
    else:
        return None

FQN_DELIMITER = "."

MEMBER_DELIMITER="_"

class BoolMarker(object):
    def __init__(self):
        self.value = False
    def __enter__(self):
        self.value = True
        return self
    def __exit__(self, type, value, traceback):
        self.value = False
    def __bool__(self) -> bool:
        return self.value
    def __str__(self) -> str:
        return str(self.value)
    def __repr__(self) -> str:
        return repr(self.value)

class CountMarker(object):
    def __init__(self, initial_value: int = 0):
        self.value = initial_value
    def __enter__(self):
        self.value += 1
        return self
    def __exit__(self, type, value, traceback):
        self.value -= 1
    def __coerce__(self, other) -> Optional[Tuple[int]]:
        if not type(other) is int:
            return None
        return (self.value, other)
    def __int__(self) -> int:
        return self.value

class ContextMarker(object):
    def __init__(self, target_module: 'Module', context: str):
        self.target_module = target_module
        self.context = context
    def __enter__(self):
        self.target_module.set_context(self.context)
        return self
    def __exit__(self, type, value, traceback):
        self.target_module.set_context(None)

def assign_levels(objects: Iterable[Any], object: Any, object_to_level: Dict[Any, int], level_to_objects: Dict[int, List[Any]], get_dependencies: Callable) -> int:
    def assign_level(object, level):
        object_to_level[object] = level
        if level not in level_to_objects:
            level_to_objects[level] = []
        level_to_objects[level].append(object)
        return level

    if object not in object_to_level:
        dependencies = get_dependencies(object)
        if len(dependencies) == 0:
            return assign_level(object, 0)
        else:
            level = max(assign_levels(objects, dependency, object_to_level, level_to_objects, get_dependencies) + 1 for dependency in dependencies)
            return assign_level(object, level)
    return object_to_level[object]

def sort_by_level(objects: Iterable[Any], get_dependencies: Callable, reverse: bool = False) -> List[Any]:
    object_to_level: Dict[Any, int] = {}
    level_to_objects: Dict[int, List[Any]] = {}
    for object in objects:
        assign_levels(objects, object, object_to_level, level_to_objects, get_dependencies)
    ret_val = []
    levels = list(level for level in level_to_objects.keys())
    levels.sort(reverse = reverse)
    for level in levels:
        ret_val += level_to_objects[level]
    return ret_val

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


def implicit_adapt(input: 'Junction', output_type: 'NetType') -> 'Junction':
    return adapt(input, output_type, implicit=True, force=False)


def explicit_adapt(input: 'Junction', output_type: 'NetType') -> 'Junction':
    return adapt(input, output_type, implicit=False, force=False)


def cast(input: 'Junction', output_type: 'NetType') -> 'Junction':
    return adapt(input, output_type, implicit=False, force=True)

def adapt(input: 'Junction', output_type: 'NetType', implicit: bool, force: bool) -> 'Junction':
    """
    Creates an adaptor instance if needed to convert input to output_type.
    Returns the generated output port. If such adaptation is not possible, raises an exception
    """
    if output_type == input.get_net_type():
        return input
    try:
        ret_val = output_type.adapt_from(input, implicit, force)
        if ret_val is None:
            raise Exception # Force the other path to execute in case this one isn't supported
        return ret_val
    except:
        pass
    ret_val = input.get_net_type().adapt_to(output_type, input, implicit, force)
    if ret_val is None:
        raise SyntaxErrorException(f"Can't generate adaptor from {input.get_net_type()} to {output_type} for port {input}")
    return ret_val

def product(__iterable: Iterable[int]):
    from functools import reduce
    return reduce((lambda x, y: x * y), __iterable)

def common_superclass(*args, **kwargs) -> object:
    """
    Returns the most specialized common superclass of all supplied argiments
    """
    all_args = list(args) + list(kwargs.values())
    assert len(all_args) > 0

    from inspect import getmro
    candidates = list(getmro(type(all_args[0])))
    for arg in all_args[1:]:
        bases = set(getmro(type(arg)))
        candidates = [candidate for candidate in candidates if candidate in bases]
        if len(candidates) == 1:
            assert candidates[0] is object
            return candidates[0]
    assert candidates[0] is not object
    return candidates[0]

def get_common_net_type(junctions: Sequence['Junction'], partial_results: bool = False) -> Optional[object]:
    net_types = tuple(junction.get_net_type() for junction in junctions if not junction.is_typeless() or not partial_results)
    # If any of the types
    if (any(net_type is None for net_type in net_types) or len(net_types) == 0) and not partial_results:
        return None
    if len(net_types) == 0:
        return None
    superclass = common_superclass(*net_types)
    from .net_type import NetType
    from inspect import getmro
    if superclass in (object, NetType) or NetType not in getmro(superclass):
        junction_list_as_str = " ".join(str(junction) for junction in junctions)
        raise SyntaxErrorException(f"Ports {junction_list_as_str} don't have a common superclass.")
    return superclass

def get_caller_local_junctions(frame_cnt: int = 1) -> Dict[str, 'Junction']:
    import inspect as inspect
    caller_frame = inspect.currentframe()
    while frame_cnt > 0:
        caller_frame = caller_frame.f_back
        frame_cnt-=1
    caller_local_junctions = {}
    for name, value in caller_frame.f_locals.items():
        if (is_junction_or_member(value)) and value.allow_bind():
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
