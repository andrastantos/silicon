from typing import Union, Set, Tuple, Dict, Any, Optional, Callable, List
import sys
from collections import namedtuple
from .stack import Stack
class Tracer(object):
    ContextInfo = namedtuple("ContextInfo", ("name", "trace"))
    old_tracer: Optional[Callable] = None
    tracer_active: bool = False
    enable = Stack()
    black_list: Set[str] = {"write", "__new__","__ilshift__","__setattr__"}
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
            except:
                pass
            if not context.trace:
                return chain()
            if not func_name in Tracer.force_list:
                if func_name.startswith("__"): # Skip all dunder functions
                    return chain()
                if func_name in Tracer.black_list:
                    return chain()
            if func_name == 'write':
                # Ignore write() calls from print statements
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
                from .utils import is_junction_or_member, is_module, is_input_port, is_output_port, is_wire, first
                if is_junction_or_member(local_value):
                    header_printed = print_header()
                    junction = local_value.get_underlying_junction()
                    if junction is not None:
                        from .module import Module
                        from .port import Wire
                        junction_parent_module = junction.get_parent_module()
                        parent_module = Module._parent_modules.top()
                        same_level = junction_parent_module is parent_module
                        sub_level = junction_parent_module._impl.parent is parent_module
                        is_unused_local_wire = is_wire(junction) and junction.source is None and len(junction.sinks) == 0
                        if (same_level and not is_unused_local_wire) or (sub_level and not is_wire(junction)):
                            wire = Wire(parent_module=parent_module)
                            wire.local_name = local_name
                            if Tracer.debug_print_level > 1:
                                print(f"\tJUNCTION {wire.local_name} {id(wire):x} CREATED for {func_name}")
                            # We have to figure out the best way to splice the new wire into the junction topology.
                            # This normally doesn't matter, but interfaces are sensitive to it: they insist on a straight
                            # topology with no bifurcations as the reversed members don't know how to deal with that.
                            # The following cases are possible:
                            # 1. junction is same-level input: we splice in after
                            # 2. junction is same-level output: we splice in before
                            # 3. junction is same-level wire: we splice in before/after, doesn't matter
                            # 5. junction is sub-level input: we splice in before
                            # 6. junction is sub-level output: we splice in after
                            # 7. junction is sub-level wire: this is not supported, so leave as-is, don't try to interfere <-- this is handled in the condition above
                            if (is_input_port(junction) and same_level) or (is_output_port(junction) and sub_level) or (is_wire(junction) and same_level):
                                # splice after
                                old_sink = first(junction.sinks) if len(junction.sinks) > 0 else None
                                if Tracer.debug_print_level > 1:
                                    print(f"\tjunction {id(junction):x} connectivity:")
                                    if junction.source is not None:
                                        print(f"\t   source: {id(junction.source):x}")
                                    sinks = "; ".join(f"{id(sink):x}" for sink in junction.sinks)
                                    print(f"\t   sinks: {sinks}")
                                if old_sink is not None:
                                    if Tracer.debug_print_level > 1:
                                        print(f"\t-- splice after SETTING SOURCE OF {id(old_sink):x} to {id(wire):x} (used to be {id(old_sink.source):x})")
                                    old_sink.set_source(wire)
                                if Tracer.debug_print_level > 1:
                                    print(f"\t-- splice after SETTING SOURCE OF {id(wire):x} to {id(junction):x}")
                                wire.set_source(junction)
                            else:
                                # splice before
                                old_source = junction.source
                                if old_source is not None:
                                    if Tracer.debug_print_level > 1:
                                        print(f"\t-- splice before SETTING SOURCE OF {id(wire):x} to {id(old_source):x}")
                                    wire.set_source(old_source)
                                if Tracer.debug_print_level > 1:
                                    print(f"\t-- splice before SETTING SOURCE OF {id(junction):x} to {id(wire):x} (used to be {id(junction.source):x})")
                                junction.set_source(wire)
                        elif same_level and not is_unused_local_wire:
                            # This is an unused local wire.
                            if Tracer.debug_print_level > 0:
                                print(f"\tUNUSED_LOCAL JUNCTION {local_name} {id(junction):x} SKIPPED for {func_name}")
                        else:
                            if Tracer.debug_print_level > 0:
                                print(f"\tNON_LOCAL JUNCTION {local_name} {id(junction):x} SKIPPED for {func_name}")

                if is_module(local_value):
                    header_printed = print_header()
                    if Tracer.debug_print_level > 1:
                        print(f"\tModule {local_name} = {local_value}")
                    module = local_value
                    if module._impl.name is not None:
                        print(f"\t\tWARNING: module already has a name {module}. Not changing it")
                    else:
                        with module._impl._no_junction_bind:
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
        assert Tracer.old_tracer is None
        assert not Tracer.tracer_active, "Only a single tracer can be active at a time. Please don't call '_body' recursively!"
        Tracer.tracer_active = True
        Tracer.old_tracer = sys.getprofile()
        assert Tracer.enable.is_empty()
        Tracer.enable.push(False) # Start tracer in the disabled state (except for the first-level call)
        Tracer.context.push(Tracer.ContextInfo("__enter__", False)) # The first trace event we'll see is the return from the __enter__ call, so let's pre-populate the context stack
        Tracer.initial_entry = True
        sys.setprofile(Tracer.trace_event_handler)
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
