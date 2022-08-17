from typing import Union, Set, Tuple, Dict, Any, Optional, Callable, List
import sys
from collections import namedtuple

from .exceptions import SyntaxErrorException
from .stack import Stack
class Tracer(object):
    ContextInfo = namedtuple("ContextInfo", ("name", "trace"))
    old_tracer: Optional[Callable] = None
    tracer_active: bool = False
    enable = Stack()
    black_list: Set[str] = {"write", "print"}
    force_list: Set[str] = {}
    context = Stack()
    debug_print_level: int = 0
    initial_entry: bool = False

    @staticmethod
    def trace_event_handler(frame, event, arg):
        from .module import Module
        def chain():
            if Tracer.old_tracer is not None:
                return Tracer.old_tracer(frame, event, arg)
            return
        stack_frame = frame.f_code
        func_name = stack_frame.co_name
        line_no = frame.f_lineno
        filename = stack_frame.co_filename

        header_printed = False

        def print_header():
            if Tracer.debug_print_level > 0:
                if not header_printed:
                    print(f"In function {func_name} at {filename}:{line_no}")
                    context = tuple(c.name for c in Tracer.context)
                    print(f"Context: {'.'.join(context)}")
            return True

        if event == 'call':
            if Tracer.initial_entry:
                Tracer.initial_entry = False
                Tracer.context.push(Tracer.ContextInfo(func_name, True))
                if Tracer.debug_print_level > 2:
                    print(f">>>> {func_name} at {filename}:{line_no}")
            else:
                if Tracer.enable.is_empty():
                    enable = False
                else:
                    enable = Tracer.enable.pop()
                Tracer.context.push(Tracer.ContextInfo(func_name, enable))
                if Tracer.debug_print_level > 2:
                    if enable:
                        print(f">>>> {func_name} at {filename}:{line_no}")
                    #else:
                    #    print(f">--- {func_name} at {filename}:{line_no}")
            return chain()
        elif event == 'return':
            try:
                context = Tracer.context.pop()
                if not context.trace:
                    return chain()
            except:
                pass
            if not func_name in Tracer.force_list:
                if func_name.startswith("__"): # Skip all dunder functions
                    return chain()
                if func_name in Tracer.black_list:
                    return chain()
            if Tracer.debug_print_level > 2:
                print(f"<<<< {func_name} at {filename}:{line_no}")
            stack_frame = frame.f_code
            func_name = stack_frame.co_name
            header_printed = False
            for local_name in sorted(frame.f_locals.keys()):
                local_value = frame.f_locals[local_name]
                if local_name == "self":
                    continue
                from .utils import is_junction_base, is_module, register_local_wire
                if is_junction_base(local_value):
                    header_printed = print_header()
                    parent_module = Module.get_current_scope()
                    if parent_module is None:
                        # We can't really assert in tracer, I don't think. So we simply terminate with a nasty message
                        print(f"Traces is enabled outside of module bodies. THIS IS REALLY BAD!!!", file=sys.stderr)
                        sys.exit(-1)
                    try:
                        register_local_wire(local_name, local_value, parent_module, debug_print_level=Tracer.debug_print_level, debug_scope=func_name)
                    except SyntaxErrorException as ex:
                        print(f"{ex}", file=sys.stderr)
                        sys.exit(-1)

                elif is_module(local_value):
                    header_printed = print_header()
                    if Tracer.debug_print_level > 1:
                        print(f"\tModule {local_name} = {local_value}")
                    module = local_value
                    if module._impl.name is not None:
                        print(f"\t\tWARNING: module already has a name {module}. Not changing it")
                    else:
                        module._impl.name = local_name
            return chain()
        elif event == "c_call":
            return chain()
        elif event == "c_return":
            return chain()
        elif event == "c_exception":
            return chain()
        else:
            print_header()
            print(f"WARNING: Unknown tracer event: {event}")
            return chain()

    def __init__(self):
        pass

    def __enter__(self):
        try:
            assert Tracer.old_tracer is None
            assert not Tracer.tracer_active, "Only a single tracer can be active at a time. Please don't call '_body' recursively!"
            assert Tracer.enable.is_empty()
            Tracer.tracer_active = True
            Tracer.enable.push(False) # Start tracer in the disabled state (except for the first-level call)
            Tracer.context.push(Tracer.ContextInfo("__enter__", False)) # The first trace event we'll see is the return from the __enter__ call, so let's pre-populate the context stack
            Tracer.initial_entry = True
            Tracer.old_tracer = sys.getprofile()
            sys.setprofile(Tracer.trace_event_handler)
        except:
            if Tracer.tracer_active:
                sys.setprofile(Tracer.old_tracer)
                while not Tracer.context.is_empty():
                    Tracer.context.pop()
                while not Tracer.enable.is_empty():
                    Tracer.enable.pop()
                Tracer.old_tracer = None
                Tracer.tracer_active = False
            print("Tracer::__enter__ - throw", file=sys.stderr)
            raise

    def __exit__(self, type, value, traceback):
        sys.setprofile(Tracer.old_tracer)
        if type is None:
            assert len(Tracer.context) == 1 # We still have the __exit__ call on the context
        while not Tracer.context.is_empty():
            Tracer.context.pop()
        while not Tracer.enable.is_empty():
            Tracer.enable.pop()
        Tracer.old_tracer = None
        Tracer.tracer_active = False

class NoTrace(object):
    def __init__(self):
        pass
    def __enter__(self):
        Tracer.enable.push(False)
    def __exit__(self, type, value, traceback):
        try:
            Tracer.enable.pop()
        except IndexError:
            pass

class Trace(object):
    def __init__(self):
        pass
    def __enter__(self):
        Tracer.enable.push(True)
    def __exit__(self, type, value, traceback):
        try:
            Tracer.enable.pop()
        except IndexError:
            pass


def no_trace(func):
    def wrapper(*args, **kwargs):
        with NoTrace():
            return func(*args, **kwargs)

    return wrapper

def trace(func):
    def wrapper(*args, **kwargs):
        with Trace():
            return func(*args, **kwargs)

    return wrapper
