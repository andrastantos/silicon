from typing import Union, Set, Tuple, Dict, Any, Optional, Callable, List
import sys
from collections import namedtuple
import traceback

from .exceptions import SyntaxErrorException
from .stack import Stack
class Tracer(object):
    class ContextInfo(object):
        def __init__(self, name, trace):
            self.name = name
            self.trace = trace

    old_tracer: Optional[Callable] = None
    tracer_active: bool = False
    black_list: Set[str] = {"write", "print"}
    context = Stack()
    debug_print_level: int = 0

    @staticmethod
    def trace_event_handler(frame, event, arg):
        from .netlist import Netlist
        def chain():
            if Tracer.old_tracer is not None:
                return Tracer.old_tracer(frame, event, arg)
            return
        stack_frame = frame.f_code
        func_name = stack_frame.co_name
        line_no = frame.f_lineno
        filename:str = stack_frame.co_filename

        header_printed = False

        def is_reserved():
            # Work around PyDev debugger inserting funky calls into our trace that screws up our carefully curated enable-disable queue
            if filename.find("/pydevd/") != -1:
                return True
            if filename.find("\\pydevd\\") != -1:
                return True
            if func_name.startswith("__"): # Skip all dunder functions
                return True
            if func_name in Tracer.black_list:
                return True
            return False

        def print_header():
            if Tracer.debug_print_level > 0:
                if not header_printed:
                    print(f"In function {func_name} at {filename}:{line_no}")
                    context = tuple(c.name for c in Tracer.context)
                    print(f"Context: {'.'.join(context)}")
            return True

        if event == 'call':
            #print(f">=== {func_name} at {filename}:{line_no}")
            Tracer.context.push(Tracer.ContextInfo(func_name, False))
            return chain()
        elif event == 'return':
            try:
                _ = Tracer.context.pop()
            except:
                return chain()
            if is_reserved():
                return chain()
            if not Tracer.context.top().trace:
                #print(f"<--- {func_name} at {filename}:{line_no}")
                return chain()
            if Tracer.debug_print_level > 2:
                print(f"<<<< {func_name} at {filename}:{line_no}")
            stack_frame = frame.f_code
            func_name = stack_frame.co_name
            header_printed = False
            parent_module = Netlist.get_current_scope()
            if parent_module is None:
                # We can't really assert in tracer, I don't think. So we simply terminate with a nasty message
                print(f"Tracer is enabled outside of module bodies. THIS IS REALLY BAD!!!", file=sys.stderr)
                sys.exit(-1)

            for local_name in sorted(frame.f_locals.keys()):
                local_value = frame.f_locals[local_name]
                if local_name == "self":
                    continue
                from .utils import is_junction_base, is_module
                if is_junction_base(local_value):
                    if Tracer.debug_print_level > 1:
                        print(f"     adding local {local_name} with value {local_value}")
                    try:
                        parent_module._impl.tracer_local_wires[(func_name, local_name)] = local_value
                    except Exception as ex:
                        print(f"Can't set local wire on module from tracer. with exception {ex}. THIS IS REALLY BAD!!!", file=sys.stderr)
                        sys.exit(-1)


                elif is_module(local_value):
                    header_printed = print_header()
                    if Tracer.debug_print_level > 1:
                        print(f"\tModule {local_name} = {local_value}")
                    try:
                        parent_module._impl.tracer_local_modules[(func_name, local_name)] = local_value
                    except Exception:
                        print(f"Can't set local module on module from tracer. THIS IS REALLY BAD!!!", file=sys.stderr)
                        sys.exit(-1)
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
        self.tracer_save = None
        pass

    def __enter__(self):
        if Tracer.tracer_active:
            # The top of the context is our __enter__. We need to adjust the 'trace' property on the entry below
            my_context = Tracer.context.peek(1)
            self.tracer_save = my_context.trace
            my_context.trace = True
        else:
            assert Tracer.old_tracer is None
            Tracer.context.push(Tracer.ContextInfo("----", True)) # The first element enables tracing of direct-calls from within the 'with' block
            Tracer.context.push(Tracer.ContextInfo("__enter__", False)) # The first trace event we'll see is the return from the __enter__ call, so let's pre-populate the context stack
            Tracer.old_tracer = sys.getprofile()
            Tracer.tracer_active = True
            try:
                sys.setprofile(Tracer.trace_event_handler)
            except:
                sys.setprofile(Tracer.old_tracer)
                while not Tracer.context.is_empty():
                    Tracer.context.pop()
                Tracer.old_tracer = None
                Tracer.tracer_active = False
                raise

    def __exit__(self, type, value, traceback):
        if self.tracer_save is None:
            # We are the top-level tracer: we should uninstall
            sys.setprofile(Tracer.old_tracer)
            if type is None:
                assert len(Tracer.context) == 2 # We still have the __exit__ call on the context
            while not Tracer.context.is_empty():
                Tracer.context.pop()
            Tracer.old_tracer = None
            Tracer.tracer_active = False
        else:
            # We are a sub-tracer. The context stack should contain our __exit__ and below that the context we've modified on __enter__
            # We need to restore that
            my_context = Tracer.context.peek(1)
            my_context.trace = self.tracer_save

