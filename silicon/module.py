# We will be able to rework generic modules when https://www.python.org/dev/peps/pep-0637/ becomes reality (currently targetting python 3.10)
# Well, that PEP got rejected, so I guess there goes that...
from typing import Union, Set, Tuple, Dict, Any, Optional, List, Iterable, Generator, Sequence, Callable
import typing
from collections import OrderedDict
from .port import Junction, Port, Output, Input, Wire, sim_const
from .net_type import NetType
from .utils import convert_to_junction, BoolMarker, str_block, CountMarker, TSimEvent, ContextMarker, first
from .stack import Stack
from .tracer import Tracer, Trace, NoTrace, trace, no_trace
from .netlist import Netlist
from enum import Enum
from .ordered_set import OrderedSet
from .exceptions import SyntaxErrorException
from threading import RLock
from itertools import chain, zip_longest
from .utils import is_port, is_input_port, is_output_port, is_wire, is_junction_member, is_module, fill_arg_names, is_junction_or_member, is_junction, is_iterable, MEMBER_DELIMITER, first
from .state_stack import StateStackElement
import inspect

def has_port(module: 'Module', name: str) -> bool:
    return name in module.get_ports().keys()

class InlineBlock(object):
    def __init__(self, target_ports: Port):
        self.target_ports = target_ports
    def set_target_ports(self, target_ports: Port):
        self.target_ports = target_ports

class InlineExpression(InlineBlock):
    def __init__(self, target_port: Port, expression: str, precedence: int):
        super().__init__((target_port, ))
        self.expression = expression
        self.precedence = precedence
    def get_inline_assignments(self, back_end: 'BackEnd') -> str:
        assert len(self.target_ports) == 1
        return f"assign {first(self.target_ports).interface_name} = {self.expression};\n"
    def inline(self, scope: 'Module', netlist: 'Netlist', back_end: 'BackEnd') -> Optional[str]:
        assert len(self.target_ports) == 1
        inline_port = first(self.target_ports)
        assert not inline_port.is_composite()
        xnet = netlist.get_xnet_for_junction(inline_port)
        xnet.add_rhs_expression(scope, self.expression, self.precedence)
        inline_port_name = xnet.get_lhs_name(scope, allow_implicit=False)
        if inline_port_name is not None:
            return f"{xnet.generate_assign(inline_port_name, self.expression, back_end)}\n"
        else:
            return None


class InlineStatement(InlineBlock):
    def __init__(self, target_ports: Sequence[Port], statement = str):
        super().__init__(target_ports)
        self.statement = statement
    def get_inline_assignments(self, back_end: 'BackEnd') -> str:
        return self.statement
    def inline(self, scope: 'Module', netlist: 'Netlist', back_end: 'BackEnd') -> Optional[str]:
        return self.statement

class InlineComposite(InlineBlock):
    def __init__(self, target_port: Port, member_inlines: Sequence[InlineBlock] = []):
        super().__init__((target_port, ))
        self.member_inlines = list(member_inlines)
    def add_member_inlines(self, member_inlines: Sequence[InlineBlock]):
        self.member_inlines += member_inlines
    def get_inline_assignments(self, back_end: 'BackEnd') -> str:
        ret_val = ""
        for member in self.member_inlines:
            ret_val += member.get_inline_assignments(back_end)
        return ret_val
    def inline(self, scope: 'Module', netlist: 'Netlist', back_end: 'BackEnd') -> Optional[str]:
        ret_val = ""
        for member in self.member_inlines:
            member_inline = member.inline(scope, netlist, back_end)
            if member_inline is None:
                ret_val = None
            if ret_val != None:
                ret_val += member_inline
        return ret_val

class GlobalSymbolTable(object):
    def __init__(self):
        self.modules: Dict[str, Module] = OrderedDict()
        self.variants: Dict[type, Set[Module]] = OrderedDict()
    def add_module(self, module: 'Module') -> None:
        self.modules
    def find_module(self, module: 'Module') -> bool:
        pass

class Module(object):
    _in_new = BoolMarker()
    _in_new_lock = RLock()
    # Since we don't want to muddy the RTL description with explicit parentage passing, we need to pass this information from parents' body() to childs __init__ over a global.
    # Not the most elegant, but I had no better idea. This however prevents true multi-threaded behavior
    _parent_modules = Stack()

    ignore_caller_filenames = ["tracer.py", "module.py", "number.py", "port.py", "utils.py"]
    ignore_caller_libs= ["silicon"]
    ignore_callers = ["wrapper", "__init__"]

    class Context(StateStackElement):
        def __init__(self, context: 'Module'):
            self.context = context

    def __new__(cls, *args, **kwargs):
        with cls._in_new_lock:
            if not cls._in_new:
                # For a non-generic module, all parameters are passed on to the __call__ function.
                # If we don't have *any* parameters passed in however, we'll return the object itself.
                if len(args) == 0 and len(kwargs) == 0:
                    ret_val = super().__new__(cls)
                    return ret_val
                else:
                    # Need to call __call__, but for that, we need an instance first.
                    with cls._in_new:
                        instance = cls()
                    ret_val = instance(*args, **kwargs)
                    return ret_val
            else:
                return super().__new__(cls)

    def __init__(self, *args, **kwargs):
        self.custom_parameters = OrderedDict()
        self._impl = Module.Impl(self, *args, **kwargs)
        self._impl._init_phase2(*args, **kwargs)

    def get_sub_modules(self) -> Sequence['Module']:
        return self._impl.get_sub_modules()
    def get_ports(self) -> 'OrderedDict[str, Port]':
        return self._impl.get_ports()
    def get_inputs(self) -> 'OrderedDict[str, Port]':
        return self._impl.get_inputs()
    def get_positional_inputs(self) -> 'OrderedDict[str, Port]':
        return self._impl.get_positional_inputs()
    def get_outputs(self) -> 'OrderedDict[str, Port]':
        return self._impl.get_outputs()
    def get_positional_outputs(self) -> 'OrderedDict[str, Port]':
        return self._impl.get_positional_outputs()
    def get_wires(self) -> 'OrderedDict[str, Wire]':
        return self._impl.get_wires()
    def get_junctions(self) -> 'OrderedDict[str, Junction]':
        return self._impl.get_junctions()



    def __call__(self, *args, **kwargs) -> Union[Port, Tuple[Port]]:
        def do_call() -> Union[Port, Tuple[Port]]:
            my_positional_inputs = tuple(self._impl.get_positional_inputs().values())
            for idx, arg in enumerate(args):
                arg_junction = convert_to_junction(arg) if arg is not None else None
                if idx >= len(my_positional_inputs) and not self._impl._in_create_port:
                    input_cnt = len(my_positional_inputs)
                    self._impl._create_positional_port(idx, arg_junction.get_net_type() if arg_junction is not None else None)
                    if len(self._impl.get_inputs()) == input_cnt:
                        raise SyntaxErrorException(f"Module {self} doesn't support dynamic creation of more positional ports")
                    my_positional_inputs = tuple(self._impl.get_positional_inputs().values())
                if arg_junction is not None:
                    my_positional_inputs[idx].bind(arg_junction)
            for arg_name, arg_value in kwargs.items():
                arg_junction = convert_to_junction(arg_value) if arg_value is not None else None
                if not has_port(self, arg_name) and not self._impl._in_create_port:
                    self._impl._create_named_port(arg_name, arg_junction.get_net_type() if arg_junction is not None else None)
                if arg_junction is not None:
                    getattr(self, arg_name).bind(arg_junction)
            ret_val = tuple(self._impl.get_outputs().values())
            if len(ret_val) == 1:
                return ret_val[0]
            return ret_val

        if self._impl.parent is not None:
            ret_val = do_call()
            return ret_val
        else:
            return do_call()

    def __setattr__(self, name, value) -> None:
        if "_impl" not in self.__dict__:
            super().__setattr__(name, value)
        elif "setattr__impl" in self._impl.__dict__:
            self._impl.setattr__impl(name, value, super().__setattr__)
        else:
            super().__setattr__(name, value)

    def __getattr__(self, name) -> Any:
        # This gets called in the following situation:
        #    my_module.dynamic_port <<= 42
        # where dynamic_port is someting that normally would get created by create_named_port.
        # TODO: what to do during simulation??
        if self._impl._no_port_create_in_get_attr:
            raise AttributeError
        if self._impl.active_context() != "elaboration":
            raise AttributeError
        port = self._impl._create_named_port(name)
        if port is None:
            raise AttributeError
        return port

    def create_named_port(self, name: str) -> Optional[Port]:
        """
        Called from the framework when unknown ports are accessed. This allows for dynamic port creation, though the default is to do nothing.
        Port creation should be as restrictive as possible and for any non-supported name, return None.
        This allows for regular attribute creation for non-port attributes.
        NOTE: create_named_port should return the created port object instead of directly adding it to self
        """
        return None

    def create_positional_port(self, idx: int) -> Optional[Union[str, Port]]:
        """
        Called from the framework when unknown ports are accessed. This allows for dynamic port creation, though the default is to do nothing.
        Port creation should be as restrictive as possible and for any non-supported index, do nothing.

        NOTE: create_positional_port should return the created port object instead of directly adding it to self

        Returns the name of the port as well as the port object.
        """
        return None

    def body(self) -> None:
        pass
    def construct(self) -> None:
        pass

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: 'Module') -> Generator[InlineBlock, None, None]:
        """
        If inlining on a per-output level is supported, yields a tuple for each output containing either an inline statement or expression.

        An inline expression is something that can be inlined into other expressions, while an inline statement is something that can be placed in the
        encompassing block.

        For example, an and gate, would return '(ina & inb)' as an inline expression.
        It could also chose to support an inline statement and return 'assign out = ina & inb;\n'.

        A register would not support inline expressions and would return 'always @(posedge clk) out <= in;\n" as an inline statement.

        The default implementation is to not support inlineing, thus not yielding anything.
        """
        return
        # NOTE: the hack of the unreachable yield expression to inform the Python interpreter of the fact that the function is a
        #       generator even though it never actually yields anything.
        yield

    def simulate(self) -> TSimEvent:
        """
        Called when the simulation starts.
        Should yield:
            - A port or a sequence of port objects to wait on. Any change of any of the listed ports will trigger the execution of the rest of the function.
            - An integer to wait for the specified amount of time.
        If the function ever returns, it is assumed that the module does't need any more notifications
        and will not be called again in the current simulation run.

        This method needs to be overwritten for all modules which include custom behavior.
        Because signal value propagation happens automatically through the netlist during simulation,
        if a module contains a pure netlist (like most modules do), the 'simulate' function can and should
        be left empty.

        Apart from primitives, most test-bench modules will implement this method to drive stimulus and test resposnes.
        """
        pass
    def is_combinational(self) -> bool:
        """
        Returns True if the module is purely combinational, False otherwise

        Default implementation is to return False, as that's the safe assumption.
        """
        return False

    def __str__(self) -> str:
        if hasattr(self, "_impl"):
            return self._impl.get_diagnostic_name(add_location = True)
        else:
            return super().__str__()

    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        """
        Default implementation is to generate recursive sub-modules. Primitives will override this behavior to terminate the recursion
        """

        assert back_end.language == "SystemVerilog", "Unknown back-end specified: {}".format(back_end.language)
        ret_val = ""
        """
        The type of module interface we're after is something like this:
        Module alu (
            input  logic [g_width-1:0] p_in_a,
            input  logic [g_width-1:0] p_in_b,
            input  logic [7:0]         p_in_op,

            output logic [g_width-1:0] p_out_result
        );
        """

        assert back_end.language == "SystemVerilog"
        rtl_header = ""
        rtl_inline_assignments = ""
        rtl_instantiations = ""
        rtl_wire_definitions = ""
        rtl_wire_assignments = ""

        # Iterate through all the sub-modules and collect all their outputs (which will need wires)
        # Also create instance names for each sub-module
        # TODO: Iterate through all self ports, see if aliases need to be created. If so, generate required
        #       signals and assign statements
        # TODO: for multiple aliases, shouldn we generate 'assign' or 'alias' statements?

        # First, we iterate through all the sub-modules and either generate instances or record inline expressions.
        # This becomes the core of the module RTL, but needs to be preceded by all the wire definitions and
        # followed by some residual assignments

        rtl_header = self._impl.generate_module_header(back_end)

        # We support inlining, but for some reason we're asked to generate a module. In that case we simply inline all of our outputs
        # into our body...
        self_inline_support = False
        for inline_block in self.get_inline_block(back_end, self):
            self_inline_support = True
            rtl_inline_assignments += inline_block.get_inline_assignments(back_end)

        if not self_inline_support:
            # Mark all inputs assigned and all outputs used in this scope.
            interface_port_names = set()
            for port_name, port in self.get_ports().items():
                xnets = self._impl.netlist.get_xnets_for_junction(port, port_name)
                for name, (xnet, junction) in xnets.items():
                    if is_output_port(junction):
                        xnet.use_name(self, name)
                    elif is_input_port(junction):
                        xnet.assign_name(self, name)
                    else:
                        assert False
                    interface_port_names.add(name) # This used to be port.interface_name. There's no direct equivalent for it in this new world though...

            for sub_module in self._impl._sub_modules:
                has_inline_support = False
                for inline_block in sub_module.get_inline_block(back_end, self):
                    has_inline_support = True
                    for inline_port in inline_block.target_ports:
                        assert is_output_port(inline_port)
                    inline_str = inline_block.inline(self, self._impl.netlist, back_end)
                    if inline_str is not None:
                        rtl_inline_assignments += inline_str
                if not has_inline_support:
                    module_class_name = self._impl.netlist.get_module_class_name(sub_module)
                    assert module_class_name is not None

                    if rtl_instantiations != "":
                        rtl_instantiations += "\n"
                    rtl_instantiations += f"{module_class_name} {sub_module._impl.name} (\n"
                    sub_module_ports = sub_module.get_ports()
                    last_port_idx = len(sub_module_ports) - 1
                    for idx, (sub_module_port_name, sub_module_port) in enumerate(sub_module_ports.items()):
                        if sub_module_port.is_deleted():
                            continue
                        if sub_module_port.is_composite():
                            members = sub_module_port.get_all_member_junctions(False)
                            last_sub_idx = len(members)
                            for sub_idx, sub_module_port_member in enumerate(members):
                                if is_output_port(sub_module_port_member):
                                    source_str = sub_module_port_member.get_lhs_name(back_end, self)
                                elif is_input_port(sub_module_port_member):
                                    source_str, _ = sub_module_port_member.get_rhs_expression(back_end, self)
                                else:
                                    assert False
                                rtl_instantiations += back_end.indent(f".{sub_module_port_member.interface_name}({source_str})")
                                if idx != last_port_idx or sub_idx != last_sub_idx:
                                    rtl_instantiations += ","
                                rtl_instantiations += "\n"
                            rtl_instantiations += "\n"
                        else:
                            if is_output_port(sub_module_port):
                                source_str = sub_module_port.get_lhs_name(back_end, self)
                            elif is_input_port(sub_module_port):
                                source_str, _ = sub_module_port.get_rhs_expression(back_end, self)
                            else:
                                assert False
                            rtl_instantiations += back_end.indent(f".{sub_module_port_name}({source_str})")
                            if idx != last_port_idx:
                                rtl_instantiations += ","
                            rtl_instantiations += "\n"
                    while rtl_instantiations[-1] in "\n,":
                        rtl_instantiations = rtl_instantiations[:-1]
                    rtl_instantiations += "\n);\n"
                if not has_inline_support and not self._impl._body_generated:
                    sub_module._impl._generate_needed = True

            # Next, generate all the required wire definitions.
            for xnet in self._impl.netlist.get_xnets_for_module(self):
                if xnet.get_net_type() is not None:
                    xnet_rhs_expression, _ = xnet.get_rhs_expression(self, back_end)
                    names = xnet.get_explicit_names(self, add_used=True, add_assigned=True, exclude_assigned=False)
                    if names is not None:
                        for name in names:
                            if name not in interface_port_names:
                                rtl_wire_definitions += f"{xnet.get_net_type().generate_type_ref(back_end)} {name};\n"
                    names = xnet.get_explicit_names(self, add_used=True, add_assigned=False, exclude_assigned=True)
                    if names is not None:
                        for name in names:
                            rtl_wire_assignments += f"{xnet.generate_assign(name, xnet_rhs_expression, back_end)}\n"

        ret_val = (
            str_block(rtl_header, "", "\n\n") +
            str_block(back_end.indent(rtl_wire_definitions), "", "\n") +
            str_block(back_end.indent(rtl_inline_assignments), "", "\n") +
            str_block(back_end.indent(rtl_instantiations), "", "\n") +
            str_block(back_end.indent(rtl_wire_assignments), "", "") +
            "endmodule"
        )
        return ret_val

    def generate_module_header(self, back_end: 'BackEnd') -> str:
        return self._impl.generate_module_header(back_end)

    class SymbolTable(object):
        def __init__(self):
            self._symbol_table: Dict[str, Any] = OrderedDict()
            self._base_names: Dict[str, int] = OrderedDict()
            # pre-populate reserved names into _base_names makes sure that those will not be used.
            from .back_end import get_reserved_names
            for name in get_reserved_names():
                self._base_names[name] = 0
        def is_reserved_name(self, name) -> bool:
            from .back_end import get_reserved_names
            return name in get_reserved_names()
        def register_symbol(self, base_name: str, object: Any, delimiter: str = "_") -> str:
            if base_name not in self._base_names:
                self._base_names[base_name] = 0
                name = base_name
            else:
                idx = self._base_names[base_name] + 1
                self._base_names[base_name] = idx
                name = base_name + delimiter + str(idx)
            assert name not in self._symbol_table
            self._symbol_table[name] = object
            return name
        def replace_symbol(self, name: str, object: Any) -> Any:
            ret_val = self._symbol_table[name]
            self._symbol_table[name] = object
            return ret_val
        def get_object(self, name: str) -> Any:
            ret_val = self._symbol_table[name]
            return ret_val

    class Impl(object):

        def __init__(self, true_module: 'Module', *args, **kwargs):
            """
            For non-generic modules, init is always called with no arguments. The arguments here are only filled-in
            for generic modules. However, since this is not a problem to specifty args and kwargs here and since
            all that happens with them is that they're passed through to the 'construct' call, we can leave it as-is.
            """
            import inspect
            self._no_junction_bind = BoolMarker()
            with self._no_junction_bind:
                import os
                import pathlib
                # We have to work around a problem under windows where subst can create a confusion about drive letters and various paths pointing to the same file
                try:
                    class_path = pathlib.Path(inspect.getfile(true_module.__class__)).absolute().resolve()
                    try:
                        cur_path = pathlib.Path().absolute().resolve()
                        self._class_filename = str(class_path.relative_to(cur_path))
                    except ValueError:
                        self._class_filename = str(class_path)
                except:
                    self._class_filename = "<unknown>"
                current_frame = inspect.currentframe()
                current_code = current_frame.f_code
                caller_frame = current_frame.f_back
                self._parent_local_junctions = {}
                self._true_module = true_module
                try:
                    while True:
                        caller_code = caller_frame.f_code
                        # FIXME: should this not be in the 'if' below? If it is, what happens if we never find an acceptable parent frame?
                        self._filename = caller_code.co_filename
                        from pathlib import Path
                        filepath = Path(self._filename).absolute()
                        filename = str(filepath.name)
                        lib = str(filepath.parent.name)
                        self._lineno = caller_frame.f_lineno
                        self._function = caller_code.co_name
                        if self._function not in Module.ignore_callers and filename not in Module.ignore_caller_filenames and lib not in Module.ignore_caller_libs:
                            for name, value in caller_frame.f_locals.items():
                                if (is_junction_or_member(value)) and value.allow_auto_bind():
                                    self._parent_local_junctions[name] = value
                            break
                        new_caller_frame = caller_frame.f_back
                        del caller_frame
                        caller_frame = new_caller_frame
                finally:
                    del caller_frame
                    del current_frame

                #print(f"================= module init called from: {self._filename}:{self._lineno} for module {type(self)}")
                self._context = None
                self.setattr__impl = self.__setattr__normal
                self._inside = BoolMarker()
                self._in_generate = BoolMarker()
                self._in_elaborate = ContextMarker(self, "elaboration")
                self._in_create_port = BoolMarker()
                self._in_construct = BoolMarker()
                self._in_set_attr_no_bind = BoolMarker()
                self._no_port_create_in_get_attr = BoolMarker()
                self._frozen_port_list = False
                self._ports = OrderedDict()
                self._inputs = OrderedDict()
                self._positional_inputs = OrderedDict()
                self._outputs = OrderedDict()
                self._positional_outputs = OrderedDict()
                self._wires = OrderedDict()
                self._junctions = OrderedDict()
                self._local_wires = [] # A list of all the wires declared in the body of the module
                self._generate_needed = False # Set to True if body generation is needed, False if not (that is if module got inlined)
                self._body_generated = False # Set to true if a body was already generated. This prevents body generation, even if _generate_needed is set
                self.name = None
                self.has_explicit_name = False
                #self._sub_modules = OrderedSet()
                self._sub_modules = []
                self._unordered_sub_modules = [] # Sub-modules first get inserted into this list. Once an output of a sub-module is accessed, it is moved into _sub_modules. Finally, when all is done, the rest of the sub-modules are moved over as well.
                if not Module._parent_modules.is_empty():
                    parent = Module._parent_modules.top()
                    parent._impl.register_sub_module(self._true_module)
                    self.netlist = parent._impl.netlist
                    self.parent = parent
                    self.set_context(self.parent._impl.active_context())
                else:
                    self.netlist = Netlist(self._true_module)
                    self.parent = None

        def _init_phase2(self, *args, **kwargs):
            with self._no_junction_bind:
                with self._inside:
                    from copy import deepcopy

                    def ports(m: Union['Module', type]) -> Tuple[Tuple[Union[str, Port]]]:
                        ret_val = []
                        #for name in dir(m):
                        #    val = getattr(m,name)
                        from inspect import getmro
                        classes = getmro(m)
                        for cls in classes:
                            for name, val in cls.__dict__.items():
                                if is_port(val):
                                    ret_val.append((name, val))
                        return tuple(ret_val)

                    from .back_end import get_reserved_names
                    for (port_name, port_object) in ports(type(self._true_module)):
                        if port_name in get_reserved_names():
                            raise SyntaxErrorException(f"Class {self} uses reserved name as port definition {port_name}")
                        if port_object.source is not None:
                            raise SyntaxErrorException(f"Class {self} has a port definition {port_name} with source already bound")
                        if len(port_object.sinks) != 0:
                            raise SyntaxErrorException(f"Class {self} has a port definition {port_name} with sinks already bound")
                        if port_object.get_parent_module() is not None:
                            raise SyntaxErrorException(f"Class {self} has a port definition {port_name} with parent module already assigned")
                        instance_port: Port = deepcopy(port_object)
                        # We need to use deepcopy to get all the important
                        # members, such as source/sinks/BoolMarker objects
                        # de-duplicated. However we don't want to create
                        # a bunch of duplicate types, so override the reference
                        # to the newly created net_type
                        del instance_port._net_type
                        instance_port._net_type = port_object._net_type
                        instance_port.set_parent_module(self._true_module)
                        setattr(self._true_module, port_name, instance_port)
                        #print("Creating instance port with name: {} and type {}".format(port_name, port_object))
                    #print("module {} is created".format(type(self)))
                    # Store construct arguments locally so we can compare them later for is_equivalent
                    (self._construct_args, self._construct_kwargs) = fill_arg_names(self._true_module.construct, args, kwargs)
                    with self._in_construct:
                        with Module._parent_modules.push(self._true_module):
                            with Module.Context(self):
                                with Trace():
                                    self._true_module.construct(*self._construct_args, **self._construct_kwargs)
                        for port in self.get_ports().values():
                            if port._auto:
                                port.find_cadidates()

                # Get rid of references to parent locals: that's really a cheezy way to extend the lifetime of those objects.
                # This class member is only used during the 'construct' call above, if at all. The only function using this
                # member is 'get_auto_port_to_bind', which is protected against being called from anywhere else but 'construct'.
                del self._parent_local_junctions
            #show_callers_locals()

        def set_context(self, context: str) -> None:
            # Must be called late enough in "__init__" so that the various attributes are already set.
            for sub_module in self._sub_modules:
                sub_module._impl.set_context(context)
            for junction in self.get_junctions().values():
                junction.set_context(context)
            for wire in self._local_wires:
                wire.set_context(context)
            self._context = context
            if context == "simulation":
                self.setattr__impl = self.__setattr__sim
            else:
                self.setattr__impl = self.__setattr__normal

        def get_sub_modules(self) -> Sequence['Module']:
            return self._sub_modules

        def order_sub_module(self, sub_module: 'Module'):
            """
            Moves a module from the unordered set of sub-modules to the ordered one.
            The reason the two lists exist is that sub-modules are created in lexical
            order (the order they appear in the body()), but that order of sub-module
            evaluation might result in a lot of extra, unnecessary temporary wire
            definition during RTL generation.
            So, instead of keeping that order, the sub-module order is re-arranged based
            in the order (any of) their outputs is bound. This in many cases ensures
            that modules appear in self._sub_modules in the order they are used, not
            in the order they are defined, resulting much better inlining behavior.

            The function is safe to call with the same module multiple times: after
            the first call, it becomes a no-op.
            """
            try:
                if sub_module in self._unordered_sub_modules:
                    self._unordered_sub_modules.remove(sub_module)
                    self._sub_modules.append(sub_module)
            except AttributeError:
                # It is possible that this function is called after _unordered_sub_modules
                # gets deleted. Let's make sure we didn't forget anybody, but otherwise that's OK.
                assert sub_module in self._sub_modules
        def register_sub_module(self, sub_module: 'Module'):
            assert is_module(sub_module)
            try:
                self._unordered_sub_modules.append(sub_module)
            except AttributeError:
                # It is possible that we get called, after _unordered_sub_modules gets deleted.
                # The case for that is the following:
                # 1. There is a sub-module, whos output is bound to a typed junction within this module.
                # 2. That sub-module then gets called, and it establishes a new output type for its output port.
                # 3. The outputs net type is changed, using set_net_type.
                # 4. This type-change process creates an Adaptor between the output and its previous sink(s)
                # 5. This Adaptor gets injected *into the scope of this module* even though it got created within
                #    the sub-module.
                # 6. Since this process happens after body and _body for this module terminated, the
                #    _unordered_sub_modules attribute is already deleted.
                # To make sure this process succeeds, we'll simply include these type-conversion modules into our
                # sub-module list.
                self._sub_modules.append(sub_module)
        def get_ports(self) -> 'OrderedDict[str, Port]':
            return self._ports
        def get_inputs(self) -> 'OrderedDict[str, Port]':
            return self._inputs
        def get_positional_inputs(self) -> 'OrderedDict[str, Port]':
            return self._positional_inputs
        def get_outputs(self) -> 'OrderedDict[str, Port]':
            return self._outputs
        def get_positional_outputs(self) -> 'OrderedDict[str, Port]':
            return self._positional_outputs
        def get_wires(self) -> 'OrderedDict[str, Wire]':
            return self._wires
        def get_junctions(self) -> 'OrderedDict[str, Junction]':
            return self._junctions
        def __get_instance_name(self) -> str:
            if self.parent is None and self.name is None:
                return type(self).__name__
            assert self.name is not None, f"Node {self} somehow doesn't have a name. Maybe didn't elaborate???"
            return self.name
        def get_fully_qualified_name(self) -> str:
            from .utils import FQN_DELIMITER
            node = self
            name = self.__get_instance_name()
            while node.parent is not None:
                node = node.parent._impl
                name = node.__get_instance_name() + FQN_DELIMITER + name
            return name
        def get_diagnostic_name(self, add_location: bool = True) -> str:
            from .utils import FQN_DELIMITER
            node = self
            if self.name is None:
                name = f"<unnamed:{type(self).__name__}>"
            else:
                name = self.name
            while node.parent is not None:
                node = node.parent._impl
                name = node.get_diagnostic_name(False) + FQN_DELIMITER + name
            if add_location:
                name += self.get_diagnostic_location(" at ")
            return name

        def get_diagnostic_location(self, prefix: str = "") -> str:
            lineno = f":{self._lineno}" if self._lineno is not None else ""
            if self._filename is not None:
                return f"{prefix}{self._filename}{lineno}"

        def __set_no_bind_attr__(self, name, value, super_setter: Callable) -> None:
            marker = self._in_set_attr_no_bind if hasattr(self, "_in_set_attr_no_bind") else BoolMarker()
            with marker:
                # If we happen to override an existing Junction object, make sure it gets removed from port lists as well
                if name in self._true_module.__dict__:
                    old_attr = self._true_module.__dict__[name]
                    if is_junction(old_attr):
                        if not is_wire(old_attr):
                            del self._ports[name]
                        if name in self._inputs:
                            del self._inputs[name]
                        elif name in self._outputs:
                            del self._outputs[name]
                        elif name in self._wires:
                            del self._wires[name]
                        else:
                            assert False
                        assert name in self._junctions
                        del self._junctions[name]
                        if name in self._positional_inputs:
                            del self._positional_inputs[name]
                        elif name in self._positional_outputs:
                            del self._positional_outputs[name]
                # If we insert a new Junction object, update the port lists as well
                if is_junction(value):
                    from .back_end import get_reserved_names
                    if name in get_reserved_names():
                        raise SyntaxErrorException(f"Class {self} uses reserved name as wire definition {name}")
                    junction = value
                    junction.set_parent_module(self._true_module)
                    assert junction.is_instantiable()
                    junction.set_interface_name(name)
                    self._junctions[name] = junction
                    if not is_wire(junction):
                        self._ports[name] = junction
                    if is_input_port(junction):
                        self._inputs[name] = junction
                        if not junction.keyword_only:
                            self._positional_inputs[name] = junction
                    elif is_output_port(junction):
                        self._outputs[name] = junction
                        if not junction.keyword_only:
                            self._positional_outputs[name] = junction
                    elif is_wire(junction):
                        self._wires[name] = junction
                        # We can't use 'in' for two reasons: we don't want __eq__, we want 'is', and we're in
                        # elaboration context so __eq__ generates a gate instead of doing the comparison anyways
                        for idx, local_wire in enumerate(self._local_wires):
                            if junction is local_wire:
                                del self._local_wires[idx]
                                break
                    else:
                        assert False, "Unknown junction object kind {}".format(type(value))
                # Finally set the actual attribute
                super_setter(name, value)
        def register_wire(self, wire: Wire) -> None:
            wire.set_parent_module(self._true_module)
            self._local_wires.append(wire)
        def active_context(self) -> str:
            return self._context

        def __setattr__sim(self, name, value, super_setter: Callable) -> None:
            if name in self.__dict__ and self.__dict__[name] is value:
                return
            else:
                # For speedup reasons, removed is_junction calls, replaced tests with exceptions
                try:
                    junction = self._true_module.__dict__[name]
                except KeyError:
                    return self.__set_no_bind_attr__(name, value, super_setter)
                try:
                    if junction is not value:
                        junction._set_sim_val(value)
                except AttributeError:
                    return self.__set_no_bind_attr__(name, value, super_setter)
                '''
                if name in self._true_module.__dict__ and is_junction(self._true_module.__dict__[name]):
                    if port is not value:
                        port._set_sim_val(value)
                else:
                    return self.__set_no_bind_attr__(name, value, super_setter)
                '''


        def __setattr__normal(self, name, value, super_setter: Callable) -> None:
            with self._no_port_create_in_get_attr:
                if name in self._true_module.__dict__ and self._true_module.__dict__[name] is value:
                    return
                if name in ("_no_junction_bind"):
                    return self.__set_no_bind_attr__(name, value, super_setter)
                if (hasattr(self, "_no_junction_bind") and self._no_junction_bind) or (is_junction(value) and self._in_create_port):
                    if is_junction(value):
                        assert value.get_parent_module() is self._true_module or value.get_parent_module() is None
                        value.set_parent_module(self._true_module)
                    return self.__set_no_bind_attr__(name, value, super_setter)
                context = self.active_context()
                if context is None:
                    return self.__set_no_bind_attr__(name, value, super_setter)
                elif context == "elaboration":
                    if is_junction(value):
                        if value.get_parent_module() is None:
                            # If the attribute doesn't exist and we do a direct-assign to a free-standing port, assume that this is a port-creation request
                            if hasattr(self._true_module, name):
                                raise SyntaxErrorException(f"Can't create new {('port', 'wire')[is_wire(value)]} {name} as that attribute allready exists")
                            return self.__set_no_bind_attr__(name, value, super_setter)
                        elif (value.get_parent_module() is self._true_module and is_input_port(value)) or (value.get_parent_module()._impl.parent is self._true_module and is_output_port(value)):
                            # We assign a port of a submodule to a new attribute. Create a Wire for it, if it doesn't exist already
                            if hasattr(self._true_module, name):
                                if not is_junction(getattr(self._true_module,name)):
                                    raise SyntaxErrorException(f"Can't create new wire {name} as that attribute allready exists")
                            else:
                                self.__set_no_bind_attr__(name, Wire(), super_setter)
                            # Flow-through to the binding portion below...
                        else:
                            # It might be that we're assigning a port to a dynamically created port: let's try creating it...
                            if not self.is_interface_frozen():
                                self._create_named_port(name)
                    if not hasattr(self._true_module, name):
                        return self.__set_no_bind_attr__(name, value, super_setter)
                    # At this point, the attribute exists, either because we've created as a junction just now or because it already was there. See if it's a junction...
                    if is_junction(getattr(self._true_module, name)):
                        try:
                        #if True:
                            junction_value = convert_to_junction(value)
                            if junction_value is None:
                                # We couldn't create a port out of the value:
                                raise SyntaxErrorException(f"couldn't bind junction to value '{value}'.")
                        except Exception as ex:
                            raise SyntaxErrorException(f"couldn't bind junction to value '{value}' with exception '{ex}'")
                        junction_inst = getattr(self._true_module, name)
                        if junction_value is junction_inst:
                            # This happens with self.port <<= something constructors: we do the <<= operator, which returns the RHS, then assign it to the old property.
                            pass
                        else:
                            #print("accessing existing port --> binding")
                            # assignment-style binding is only allowed for outputs (on the inside) and inputs (on the outside)
                            if self.is_inside():
                                if is_input_port(junction_inst):
                                    raise SyntaxErrorException(f"Can't assign to {junction_inst.junction_kind} port '{name}' from inside the module")
                            else:
                                if not is_input_port(junction_inst):
                                    raise SyntaxErrorException(f"Can't assign to {junction_inst.junction_kind} port '{name}' from outside the module")
                            junction_inst.bind(junction_value)
                    else:
                        # If the attribute is not a port, simply set it to the new value
                        return self.__set_no_bind_attr__(name, value, super_setter)
                else:
                    assert False

        def _create_named_port(self, name: str, net_type: Optional[NetType] = None) -> Optional[Port]:
            if self.is_interface_frozen():
                raise SyntaxErrorException("Can't change port list after module interface is frozen")
            with self._in_create_port:
                # To make life easier, collapse port-lists here
                port = self._true_module.create_named_port(name)
                if port is None:
                    return None
                with self._no_junction_bind:
                    setattr(self._true_module, name, port)
                if net_type is not None:
                    port.set_net_type(net_type)
                return port

        def _create_positional_port(self, idx: int, net_type: Optional[NetType]) -> None:
            if self.is_interface_frozen():
                raise SyntaxErrorException("Can't change port list after module interface is frozen")
            with self._in_create_port:
                # To make life easier, collapse port-lists here
                name_and_port = self._true_module.create_positional_port(idx)
                if name_and_port is None or name_and_port[1] is None:
                    return
                with self._no_junction_bind:
                    setattr(self._true_module, name_and_port[0], name_and_port[1])
                name_and_port[1].set_net_type(net_type)
        def is_inside(self):
            return self._inside
        def freeze_interface(self) -> None:
            with self._no_junction_bind:
                self._frozen_port_list = True
        def is_interface_frozen(self) -> bool:
            return self._frozen_port_list
        def get_auto_port_to_bind(self,port_name_list) -> Optional[Port]:
            """
            Returns a port to bind an auto-port to, if a candidate exists or None if it doesn't
            """
            assert self._in_construct, "get_auto_port_bind should only be called from 'Module.construct'"

            for name in port_name_list:
                if name in self._parent_local_junctions:
                    return self._parent_local_junctions[name].get_underlying_junction()
            if self.parent is not None:
                parent_ports = self.parent.get_ports()
                for name in port_name_list:
                    if name in parent_ports:
                        return parent_ports[name].get_underlying_junction()
                parent_wires = self.parent.get_wires()
                for name in port_name_list:
                    if name in parent_wires:
                        return parent_wires[name].get_underlying_junction()
            return None

        def _elaborate(self, hier_level, trace: bool) -> None:
            # Recursively go through each new node, add it to the netlist and call its body (which most likely will create more new nodes).
            # The algorithm does a depth-first walk of the netlist hierarchy, eventually resulting in the full network and netlist created
            self.freeze_interface()
            # Remove all wires without sources and sinks.
            for wire_name, wire in tuple(self._wires.items()):
                if not wire.is_specialized():
                    if len(wire.sinks) == 0:
                        print(f"WARNING: deleting unused wire: {wire_name} in module {self._true_module}")
                        self._wires.pop(wire_name)
                        self._junctions.pop(wire_name)
                    else:
                        raise SyntaxErrorException(f"Wire {wire_name} is used without a source")

            assert len(self._local_wires) == 0

            with self._in_elaborate:
                self._body(trace) # Will create all the sub-modules

            for wire in tuple(self._local_wires):
                if len(wire.sinks) == 0 and wire.source is None:
                    print(f"WARNING: deleting unused local wire: {wire}")
                    self._local_wires.remove(wire)

            for sub_module in self._sub_modules:
                # handle any pending auto-binds
                for port in sub_module.get_ports().values():
                    if port._auto:
                        port.auto_bind() # If already bound, this is a no-op, so it's safe to call it multiple times

            # Go through each sub-module in a loop, and finalize their interface until everything is frozen

            def propagate_net_types():
                incomplete_junctions = OrderedSet(junction for junction in chain(self.get_junctions().values(), self._local_wires) if not junction.is_specialized() and junction.source is not None)
                changes = True
                while len(incomplete_junctions) > 0 and changes:
                    changes = False
                    for junction in tuple(incomplete_junctions):
                        if junction.source.is_specialized():
                            junction.set_net_type(junction.source.get_net_type())
                            changes = True
                            incomplete_junctions.remove(junction)
                return

            incomplete_sub_modules = OrderedSet(self._sub_modules)
            changes = True
            while len(incomplete_sub_modules) > 0 and changes:
                changes = True
                # Propagate types from submodule ports to wires. Keep propagating until we can't do anything more.
                propagate_net_types()

                changes = False
                for sub_module in tuple(incomplete_sub_modules):
                    # propagate all newly assigned ports
                    for input in sub_module.get_inputs().values():
                        if not input.is_specialized() and input.source is not None and input.source.is_specialized():
                            input.set_net_type(input.source.get_net_type())
                    all_inputs_specialized = all(tuple(input.is_specialized() or not input.has_driver() for input in sub_module.get_inputs().values()))
                    if all_inputs_specialized:
                        with Module.Context(sub_module._impl):
                            sub_module._impl._elaborate(hier_level + 1, trace)
                        changes = True
                        incomplete_sub_modules.remove(sub_module)

            propagate_net_types()
            if len(incomplete_sub_modules) != 0:
                # Collect all nets that don't have a type, but must to continue
                input_list = []
                for sub_module in tuple(incomplete_sub_modules):
                    input_list += (input for input in sub_module.get_inputs().values() if not (input.is_specialized() or not input.has_driver()))
                if len(input_list) > 10:
                    list_str = "\n    ".join(i.get_diagnostic_name() for i in input_list[:5]) + "\n    ...\n    " + "\n    ".join(i.get_diagnostic_name() for i in input_list[-5:])
                else:
                    list_str = "\n    ".join(i.get_diagnostic_name() for i in input_list)
                raise SyntaxErrorException(f"Can't determine net types for:\n    {list_str}")

            # Propagate output types, if needed
            for output in self.get_outputs().values():
                if not output.is_specialized():
                    if output.source is not None:
                        if output.source.is_specialized():
                            output.set_net_type(output.source.get_net_type())
                        else:
                            raise SyntaxErrorException(f"Output port {output} is not fully specialized after body call. Can't finalize interface")
            assert all((output.is_specialized() or output.source is None) for output in self.get_outputs().values())

        def elaborate(self, *, add_unnamed_scopes: bool = False) -> Netlist:

            assert self not in self.netlist.modules, f"Module {self._true_module} has already been elaborated."
            assert self.parent is None, "Only top level modules can be elaborated"

            self.freeze_interface()

            # Give top level a name and mark it as user-assigned.
            if self.name is None:
                self.name = type(self._true_module).__name__
                self.has_explicit_name = True

            all_inputs_specialized = all(tuple(input.is_specialized() for input in self.get_inputs().values()))
            with Module.Context(self):
                if not all_inputs_specialized:
                    raise SyntaxErrorException(f"Top level module must have all its inputs specialized before it can be elaborated")
                self._elaborate(hier_level=0, trace=True)
            self.netlist._post_elaborate(add_unnamed_scopes)
            return self.netlist

        def _body(self, trace: bool = True) -> None:
            """
            Called from the framework as a wrapper for the per-module (class) body method
            """
            with self._inside:
                with Module._parent_modules.push(self._true_module):
                    assert self.is_interface_frozen()
                    with Module.Context(self):
                        if trace:
                            with Tracer():
                                self._true_module.body()
                        else:
                            self._true_module.body()

                    # Finish ordering sub-modules:
                    for sub_module in self._unordered_sub_modules:
                        self._sub_modules.append(sub_module)
                    self._unordered_sub_modules.clear()

                    def finalize_slices(junction):
                        if junction.is_composite():
                            for member, _ in junction.get_member_junctions().values():
                                finalize_slices(member)
                        else:
                            junction.finalize_slices()

                    # Go through each junction and make sure their Concatenators are created if needed
                    for junction in self.get_junctions().values():
                        finalize_slices(junction)
                    for junction in self._local_wires:
                        finalize_slices(junction)

                    # The above code might have added some modules into _unordered_sub_modules, so let's clear them once again
                    for sub_module in self._unordered_sub_modules:
                        self._sub_modules.append(sub_module)

                    del self._unordered_sub_modules # This will force all subsequent module instantiations (during type-propagation) to directly go to _sub_modules


        def is_equivalent(self, other: 'module', netlist: 'NetList') -> bool:
            """
            Determines if 'self' and 'other' can share the same module body. We use the following rules:

            1. Both have exactly the same ports (names and types)
            2. Both have exactly the same wires (names and types)
            3. Both have exactly the same sub-modules (they're all equivalent) <-- THIS MEANS RECURSION!!
            4. Both have exactly the same generic arguments (as passed in to 'Construct'. Names, types and values of arguments must match)
            5. Both have exactly the same custom parameters (as determined by the custom_parameters dict member)

            If 'generate' of a module is customized, most likely this method needs customization as well.

            IMPORTANT: All implementation must be transitive. That is, if is_equivalent(A, B) and is_equivalent(B, C)
                       then is_equivalent(A, C) must be True as well.

            NOTE: in order to not call is_equivalent many many times, an equivalency-map is stored in the netlist.
            NOTE: this function will be called from Netlist in inverse hierarchy order, that is, leaf nodes first,
                  top level last. This ensures that all sub-modules within 'self' and 'other' are already visited
                  and can be quickly checked for equivalency.
            """

            if other is self:
                return True
            # Short-circuit recursion if we've seen these modules already
            my_class_name = netlist.get_module_class_name(self._true_module)
            other_class_name = netlist.get_module_class_name(other)
            if my_class_name is not None and other_class_name is not None:
                return my_class_name == other_class_name

            def are_junctions_equivalent(my_junction_name, my_junction, other_junction_name, other_junction) -> bool:
                if my_junction_name is None or my_junction is None or other_junction_name is None or other_junction is None:
                    return False
                if my_junction_name != other_junction_name:
                    return False
                # We can't really compare types directly, because each junction has a unique base-type
                if not my_junction.same_type_as(other_junction):
                    return False
                if my_junction.is_typeless() != other_junction.is_typeless():
                    return False
                if my_junction.is_typeless():
                    return True
                return my_junction.get_net_type() == other_junction.get_net_type()

            ports_are_ok = all(
                are_junctions_equivalent(my_port_name, my_port, other_port_name, other_port)
                for ((my_port_name, my_port), (other_port_name, other_port)) in zip_longest(self._true_module.get_ports().items(), other.get_ports().items(), fillvalue=(None, None))
            )
            if not ports_are_ok:
                return False
            wires_are_ok = all(
                are_junctions_equivalent(my_wire_name, my_wire, other_wire_name, other_wire)
                for ((my_wire_name, my_wire), (other_wire_name, other_wire)) in zip_longest(self._true_module.get_wires().items(), other.get_wires().items(), fillvalue=(None, None))
            )
            if not wires_are_ok:
                return False

            if len(self._sub_modules) != len(other._impl._sub_modules):
                return False
            sub_modules_are_ok = all(
                my_submodule._impl.is_equivalent(other_submodule, netlist)
                for my_submodule, other_submodule in zip(self._sub_modules, other._impl._sub_modules)
            )
            if not sub_modules_are_ok:
                return False

            if len(self._construct_args) != len(other._impl._construct_args):
                return False
            all_construct_args_are_ok = all(
                my_arg == other_arg for my_arg, other_arg in zip(self._construct_args, other._impl._construct_args)
            )
            if not all_construct_args_are_ok:
                return False

            if len(self._construct_kwargs) != len(other._impl._construct_kwargs):
                return False
            all_construct_kwargs_are_ok = all(
                my_arg_name in other._impl._construct_kwargs and my_arg == other._impl._construct_kwargs[my_arg_name] for my_arg_name, my_arg in self._construct_kwargs.items()
            )
            if not all_construct_kwargs_are_ok:
                return False

            return True


        def generate_module_header(self, back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            module_name = self.netlist.get_module_class_name(self._true_module)
            assert module_name is not None
            ret_val += "/" * 80 + "\n"
            ret_val += f"// {module_name}\n"
            ret_val += "/" * 80 + "\n"
            ret_val += f"module {module_name} (\n"
            ports = self.get_ports()
            first_port = True
            is_composite = False
            for port_name, port in ports.items():
                if not port.is_deleted():
                    port_interface_strs = port.generate_interface(back_end, port_name)
                    after_composite = is_composite
                    is_composite = len(port_interface_strs) > 1
                    for port_interface_str in port_interface_strs:
                        if first_port:
                            first_port = False
                        else:
                            ret_val += ","
                            ret_val += "\n"
                            if after_composite:
                                ret_val += "\n"
                                after_composite = False
                        ret_val += back_end.indent(f"{port_interface_str}")
            if not first_port:
                ret_val += "\n"
            ret_val += ");"
            return ret_val

        def create_symbol_table(self) -> None:
            self.symbol_table = Module.SymbolTable()

        def populate_submodule_names(self, netlist: 'Netlist') -> None:
            """
            Makes sure that every sub_module have a name and that all names are unique.
            """

            for sub_module in self._sub_modules:
                if sub_module._impl.name is not None:
                    base_instance_name = sub_module._impl.name
                    delimiter = "_"
                    sub_module._impl.has_explicit_name = True
                else:
                    base_instance_name = "u"
                    delimiter = ""
                    sub_module._impl.has_explicit_name = False
                unique_name = self.symbol_table.register_symbol(base_instance_name, sub_module, delimiter)

                if sub_module._impl.name is not None and sub_module._impl.name != unique_name:
                    print(f"WARNING: module name {sub_module._impl.name} is not unique or reserved. Overriding to {unique_name}")
                sub_module._impl.name = unique_name

        def populate_xnet_names(self, netlist: 'Netlist') -> None:
            """
            Makes sure that every xnet within the modules body have at least one name and that all names are unqiue.
            """

            # Start with all our own ports (least likely to have a name collision, and must have at least one inner name)
            for my_port_name, my_port in self.get_ports().items():
                xnets = netlist.get_xnets_for_junction(my_port, my_port_name)
                for name, (xnet, port) in xnets.items():
                    if self.symbol_table.is_reserved_name(name):
                        raise SyntaxErrorException(f"Port name {name} uses a reserved word")
                    unique_name = self.symbol_table.register_symbol(name, xnet)
                    xnet.add_name(self._true_module, unique_name, is_explicit=True, is_input=is_input_port(port))
                    if unique_name != name:
                        raise SyntaxErrorException(f"Port name {name} is not unique")
            # Look at named wires. These also have a name.
            for my_wire_name, my_wire in self.get_wires().items():
                xnets = netlist.get_xnets_for_junction(my_wire, my_wire_name)
                for name, (xnet, wire) in xnets.items():
                    if self.symbol_table.is_reserved_name(name):
                        raise SyntaxErrorException(f"Wire name {name} uses a reserved word")
                    unique_name = self.symbol_table.register_symbol(name, xnet)
                    xnet.add_name(self._true_module, unique_name, is_explicit=True, is_input=False)
                    if unique_name != name:
                        raise SyntaxErrorException(f"Wire name {name} is not unique")
                    assert wire.local_name is None or wire.local_name == name
                    assert wire.interface_name == name

            # Look through local wires (Wire objects defined in the body of the module)
            # 1. promote them to the _wire map as well as make sure they're unique
            # 2. Add them to the associated xnet
            # 3. Give them a name if they're not named (for example, if they're part of a container such as a list or tuple)
            for my_wire in tuple(self._local_wires):
                local_name = my_wire.local_name
                if local_name is None: local_name = my_wire.interface_name
                explicit = local_name is not None
                if local_name is None:
                    local_name = self.symbol_table.register_symbol("unnamed_wire", my_wire)
                # Get all the sub-nets (or the net itself if it's not a composite)
                # and handle those instead of my_wire.
                xnets = netlist.get_xnets_for_junction(my_wire, local_name)
                for name, (xnet, wire) in xnets.items():
                    # Test if name is already registered as either my_wire or xnet
                    # If it is, make sure that it is the same object.
                    # Either way, come up with a unique name, assign the xnet to that name
                    # in symbol table, and make sure the xnet is also aware of that name.
                    unique_name = None
                    try:
                        obj = self.symbol_table.get_object(name)
                        if obj is wire:
                            self.symbol_table.replace_symbol(name, xnet)
                            unique_name = name
                        elif obj is xnet:
                            assert name in xnet.get_names(self._true_module)
                            continue
                        elif not explicit:
                            raise SyntaxErrorException(f"Net name {name} already exists in module {self}, yet another explicit net tries to access it.")
                    except KeyError:
                        pass
                    if unique_name is None:
                        unique_name = self.symbol_table.register_symbol(name, xnet)
                    xnet.add_name(self._true_module, unique_name, is_explicit=explicit, is_input=False)
                    self._wires[unique_name] = wire
                    self._junctions[unique_name] = wire
                self._local_wires.remove(my_wire)
            assert len(self._local_wires) == 0

            # Finally, look through sub-module ports again, and check that all of them has at least one name
            # in their associated xnet for this scope. If not, create one.
            # NOTE: we broke this out from the previous loop to make the results stable and not depend
            #       on visitation order
            # NOTE: we only do this for outputs. The rationale is this: if there is an unconnected input
            #       on a sub-module, that net doesn't really exist in this scope. If the input *is* connected,
            #       even if we don't iterate through it here, we would eventually come accross it's driving output.
            #       (we're talking nameless wires here, so I think in almost all cases one source and one sink.)
            for sub_module in self._sub_modules:
                for sub_module_port_name, sub_module_port in sub_module.get_outputs().items():
                    # Deliberately leave the base-name component out. Once we figure it out, we can just pre-pend it...
                    xnets = netlist.get_xnets_for_junction(sub_module_port, "")
                    for name_suffix, (xnet, sub_port) in xnets.items():
                        if xnet.get_names(self._true_module) is None:
                            source_port = xnet.source
                            if source_port is None:
                                source_port = sub_port
                                source_module = sub_module
                            else:
                                source_module = source_port.get_parent_module()
                                if source_module._impl.parent is not self._true_module:
                                    source_port = sub_port
                                    source_module = sub_module
                            assert source_module is not None, "Strange: I don't think it's possible that an xnet is sourced by a floating port..."
                            name = f"{source_module._impl.name}{MEMBER_DELIMITER}{source_port.interface_name}{name_suffix}"
                            unique_name = self.symbol_table.register_symbol(name, xnet)
                            assert unique_name == name
                            xnet.add_name(self._true_module, unique_name, is_explicit=False, is_input=False) # These ports are not inputs, at least not as far is this context is concerned.


        def _generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> Optional[str]:
            if not self._generate_needed:
                return None
            with self._in_generate:
                with self._inside:
                    return self._true_module.generate(netlist, back_end)


class GenericModule(Module):
    def __new__(cls, *args, **kwargs):
        # A generic class will always pass all its arguments to __init__.
        with cls._in_new_lock:
            with cls._in_new:
                return super().__new__(cls)

class DecoratorModule(GenericModule):
    def construct(self, function: Callable, out_port_cnt: int) -> None:

        def create_output_port(port_name):
            instance_port = Output()
            setattr(self, port_name, instance_port)

        self._impl.function = function
        for idx in range(out_port_cnt):
            if out_port_cnt == 1:
                port_name = "output_port"
            else:
                port_name = f"output_port_{idx+1}"
            create_output_port(port_name)

    @no_trace
    def body(self) -> None:
        return_values = self._impl.function(*self._impl._args, **self._impl._kwargs)
        if isinstance(return_values, str) or is_junction_or_member(return_values) or not is_iterable(return_values):
            return_values = (return_values, )
        if len(return_values) != len(self._impl.get_outputs()):
            raise SyntaxErrorException(f"Modularized function returned {len(return_values)} values, where decorator declared {len(self._impl.get_outputs())} outputs. These two must match")
        for return_value, (name, output_port) in zip(return_values, self._impl.get_outputs().items()):
            # We need to do a little slight of hands here: the original output port needs to be replaced with the one returned by the function.
            # TODO: That's not true, I don't think. We can simply hook up the real outputs as sources to the previously created output
            return_port = convert_to_junction(return_value)
            if return_port is None:
                raise SyntaxErrorException(f"Modularized function must return output ports or at least things that can be turned into output ports")
            assert output_port.source is None
            output_port <<= return_port
            #for sink in output_port.sinks:
            #    assert sink.source is output_port
            #    sink.set_source(return_port)
            #delattr(self, name)
            #setattr(self, name, return_value)
            #del output_port

    def __call__(self, *args, **kwargs) -> Union[Port, Tuple[Port]]:
        # For any port argument, we'll create an input port (yet unnamed and not added to the interface)
        # For all other arguments, we simply pass them on as-is
        self._impl._args = []
        self._impl._kwargs = dict()
        ports_needing_name = {}
        for arg in args:
            if is_junction_or_member(arg):
                my_arg = Input()
                ports_needing_name[my_arg] = arg
            else:
                my_arg = arg
            self._impl._args.append(my_arg)
        # Named arguments are easy: we know what to bind them to and we know their name as well, so we need no magic
        for name, arg in kwargs:
            if is_junction_or_member(arg):
                my_arg = Input()
                setattr(self, name, my_arg)
                my_arg.bind(arg)
            else:
                my_arg = arg
            self._impl._kwargs[name] = my_arg

        # mock-bind the now created invocation arguments to the signature of the function
        # and attempt to locate the ports that need a name. This might fail if 'function' itself
        # has *args or **kwargs arguments
        from inspect import signature
        sig = signature(self._impl.function)
        bound_args = sig.bind(*self._impl._args, **self._impl._kwargs).arguments
        for name, arg in bound_args.items():
            if arg in ports_needing_name:
                setattr(self, name, arg)
                arg.bind(convert_to_junction(ports_needing_name[arg]))
                del ports_needing_name[arg]
        # Work through the remaining inputs and simply name them consecutively
        for idx, port, arg_junction in enumerate(ports_needing_name.items()):
            port_name = f"intput_{idx}"
            with self._impl._no_port_create_in_get_attr:
                if hasattr(self, port_name):
                    raise SyntaxErrorException("Can't add port {port_name} to modularized function: the attribute already exists")
            setattr(self, port_name, port)
            port.bind(convert_to_junction(arg_junction))

        ret_val = tuple(self._impl.get_outputs().values())
        if len(ret_val) == 1:
            return ret_val[0]
        return ret_val

def modularize(callable, ret_val_cnt) -> 'Module':
    return DecoratorModule(callable, ret_val_cnt)

def module(ret_val_cnt) -> Callable:
    class DecoratedFunction(object):
        def __init__(self, callable, ret_val_cnt):
            self.callable = callable
            self.ret_val_cnt = ret_val_cnt
        def __call__(self, *args, **kwargs):
            return DecoratorModule(self.callable, self.ret_val_cnt)(*args, **kwargs)
    def inner(callable) -> 'Module':
        return DecoratedFunction(callable, ret_val_cnt)

    return inner

def elaborate(top_level: Module, *, add_unnamed_scopes: bool = False) -> Netlist:
    return top_level._impl.elaborate(add_unnamed_scopes=add_unnamed_scopes)

