# We will be able to rework generic modules when https://www.python.org/dev/peps/pep-0637/ becomes reality (currently targeting python 3.10)
# Well, that PEP got rejected, so I guess there goes that...
from typing import Union, Set, Tuple, Dict, Any, Optional, List, Iterable, Generator, Sequence, Callable
import typing
from collections import OrderedDict
from .port import Junction, Port, Output, Input, Wire, JunctionBase
from .net_type import NetType, NetTypeMeta
from .utils import str_block, TSimEvent, ContextMarker, first, Context
from .tracer import Tracer, Trace, no_trace
from .netlist import Netlist
from enum import Enum
from .ordered_set import OrderedSet
from .exceptions import SimulationException, SyntaxErrorException, InvalidPortError
from threading import RLock
from itertools import chain, zip_longest
from .utils import is_port, is_input_port, is_output_port, is_wire, is_module, fill_arg_names, is_junction_base, is_iterable, MEMBER_DELIMITER, first, implicit_adapt, convert_to_junction
from .utils import ScopedAttr, register_local_wire
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
        return f"assign {first(first(self.target_ports).get_interface_names())} = {self.expression};\n"
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
    _in_new = False
    _in_new_lock = RLock()
    # Since we don't want to muddy the RTL description with explicit parentage passing, we need to pass this information from parents' body() to childs __init__ over a global.
    # Not the most elegant, but I had no better idea. This however prevents true multi-threaded behavior

    ignore_caller_filenames = ["tracer.py", "module.py", "number.py", "port.py", "utils.py"]
    ignore_caller_libs= ["silicon"]
    ignore_callers = ["wrapper", "__init__"]

    class Context(StateStackElement):
        def __init__(self, context: 'Module'):
            self.context = context

    def __new__(cls, *args, **kwargs):
        NetTypeMeta.assert_on_eq = True
        with cls._in_new_lock:
            if not cls._in_new:
                # For a non-generic module, all parameters are passed on to the __call__ function.
                # If we don't have *any* parameters passed in however, we'll return the object itself.
                if len(args) == 0 and len(kwargs) == 0:
                    ret_val = super().__new__(cls)
                    return ret_val
                else:
                    # Need to call __call__, but for that, we need an instance first.
                    with ScopedAttr(cls, "_in_new", True):
                        instance = cls()
                    ret_val = instance(*args, **kwargs)
                    return ret_val
            else:
                return super().__new__(cls)

    def __init__(self, *args, **kwargs):
        if Context.current() != Context.elaboration:
            raise SyntaxErrorException(f"Can't instantiate module outside of elaboration context")
        self.custom_parameters = OrderedDict()
        self._impl = Module.Impl(self, super().__setattr__, *args, **kwargs)
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
    def get_default_name(self, scope: object) -> str:
        return "u"



    def __call__(self, *args, **kwargs) -> Union[Port, Tuple[Port]]:
        scope = self._impl.parent
        if scope is None and (len(args) > 0 or len(kwargs) > 0):
            raise SyntaxErrorException(f"Can't use call-style instantiation with port-bindings of top level module")
        if Context.current() != Context.elaboration:
            raise SyntaxErrorException(f"Can't bind module using call-syntax outside of elaboration context")
        
        def do_call() -> Union[Port, Tuple[Port]]:
            my_positional_inputs = tuple(self._impl.get_positional_inputs().values())
            if self._impl.is_interface_frozen():
                raise SyntaxErrorException("Can't change port list after module interface is frozen")
            for idx, arg in enumerate(args):
                if idx >= len(my_positional_inputs):
                    try:
                        name, port = self.create_positional_port_callback(idx, net_type=None)
                        assert port is not None
                        if not is_port(port):
                            raise SyntaxErrorException("create_positional_port_callback should return a 'Port' instance")
                        self._impl._set_no_bind_attr(name, port)
                    except InvalidPortError:
                        raise SyntaxErrorException(f"Module {self} doesn't support dynamic creation of more positional ports")
                    my_positional_inputs = tuple(self._impl.get_positional_inputs().values())
                if arg is not None:
                    my_positional_inputs[idx].set_source(arg, scope)
            for arg_name, arg_value in kwargs.items():
                if not has_port(self, arg_name):
                    self.create_named_port(arg_name)
                if arg_value is not None:
                    getattr(self, arg_name).set_source(arg_value, scope)
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
        # Short-circuit the __set_attr__ call from the update phase of the '<<=' operator
        # This is generally safe: if nothing changes, well, nothing changes.
        if name in self.__dict__ and self.__dict__[name] is value:
            return
        if "_impl" not in self.__dict__:
            super().__setattr__(name, value)
        elif "setattr__impl" in self._impl.__dict__:
            self._impl.setattr__impl(name, value)
        else:
            super().__setattr__(name, value)

    def __getattr__(self, name) -> Any:
        # This gets called in the following situation:
        #    my_module.dynamic_port <<= 42
        # where dynamic_port is something that normally would get created by create_named_port_callback.
        # TODO: what to do during simulation??
        if Context.current() != Context.elaboration:
            raise AttributeError
        try:
            return self._impl._create_named_port(name)
        except InvalidPortError:
            raise AttributeError

    def create_named_port_callback(self, name: str, net_type: Optional['NetType'] = None) -> Optional[Port]:
        """
        Called by the framework to dynamically create ports.

        If the default mechanism of port-creation is to be used, return None.
        If the port should not be created, raise InvalidPortError
        If the port is successfully created, it should be returned, and *NOT* added to 'self' as an attribute
        """
        return None

    def create_positional_port_callback(self, idx: int, net_type: Optional['NetType'] = None) -> Tuple[str, Port]:
        """
        Called by the framework to dynamically create ports.

        If the port can't be created, raise InvalidPortError
        If the port is successfully created, it should be returned along with it's name, and *NOT* added to 'self' as an attribute
        """
        raise InvalidPortError

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
                    rtl_instantiations += f"{module_class_name} {sub_module._impl.get_name()} (\n"
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
                                rtl_instantiations += back_end.indent(f".{first(sub_module_port_member.get_interface_names())}({source_str})")
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

    def create_named_port(self, name: str, *, port_type: Optional[Callable] = None, net_type: Optional[NetType] = None) -> Port:
        if self._impl.is_interface_frozen():
            raise SyntaxErrorException(f"The interface if '{self}' is frozen. You can't add new ports anymore.")
        try:
            return self._impl._create_named_port(name, port_type=port_type, net_type=net_type)
        except InvalidPortError:
            raise SyntaxErrorException(f"Can't create port '{name}' on module '{self}'.")

    class Impl(object):
        def __init__(self, true_module: 'Module', supersetattr: Callable, *args, **kwargs):
            """
            For non-generic modules, init is always called with no arguments. The arguments here are only filled-in
            for generic modules. However, since this is not a problem to specifty args and kwargs here and since
            all that happens with them is that they're passed through to the 'construct' call, we can leave it as-is.
            """
            import inspect
            import os
            import pathlib

            self.netlist: 'Netlist' = Netlist.get_global_netlist()
            self.netlist.register_module(true_module)
            parent = self.netlist.get_current_scope()
            if parent is not None:
                parent._impl.register_sub_module(true_module)

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
            self.supersetattr = supersetattr
            # Add parents' interface and member wires
            if parent is not None:
                for name in dir(parent):
                    value = getattr(parent, name)
                    if (is_junction_base(value)) and value.allow_auto_bind():
                        self._parent_local_junctions[name] = value
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
                            if (is_junction_base(value)) and value.allow_auto_bind():
                                self._parent_local_junctions[name] = value
                        break
                    new_caller_frame = caller_frame.f_back
                    del caller_frame
                    caller_frame = new_caller_frame
            finally:
                del caller_frame
                del current_frame


            #print(f"================= module init called from: {self._filename}:{self._lineno} for module {type(self)}")
            self.setattr__impl = self._setattr__normal
            with ScopedAttr(self, "setattr__impl", self._setattr__construction):
                self._frozen_port_list = False
                self._ports = OrderedDict()
                self._inputs = OrderedDict()
                self._positional_inputs = OrderedDict()
                self._outputs = OrderedDict()
                self._positional_outputs = OrderedDict()
                self._wires = OrderedDict() # Wires that are declared as attributes. All local_wires get promoted here during XNet creation
                self._junctions = OrderedDict()
                # Local wires are wires declared in the body of the module as variables instead of attributes. Most wires are like that.
                # They don't necessarily have a name, at least initially. By the time we get to XNet creation, they certainly have one.
                # During XNet creation these wires promoted to the _wire map.
                # This map is indexed by id(wire) to work around the elaboration context __eq__ override problem.
                self._local_wires: Dict[int, Junction] = dict()
                self._generate_needed = False # Set to True if body generation is needed, False if not (that is if module got inlined)
                self._body_generated = False # Set to true if a body was already generated. This prevents body generation, even if _generate_needed is set
                #self._sub_modules = OrderedSet()
                self._sub_modules: Sequence['Module'] = []
                self._unordered_sub_modules = [] # Sub-modules first get inserted into this list. Once an output of a sub-module is accessed, it is moved into _sub_modules. Finally, when all is done, the rest of the sub-modules are moved over as well.
                self.parent = parent

        def _init_phase2(self, *args, **kwargs):
            with ScopedAttr(self, "setattr__impl", self._setattr__construction):
                from copy import deepcopy

                def ports(m: Union['Module', type]) -> Tuple[Tuple[Union[str, Port]]]:
                    ret_val = {}
                    #for name in dir(m):
                    #    val = getattr(m,name)
                    from inspect import getmro
                    classes = getmro(m)
                    for cls in reversed(classes):
                        for name, val in cls.__dict__.items():
                            if is_port(val):
                                if name in ret_val:
                                    raise SyntaxErrorException(f"Port {name} exists in one of the base-classes of {cls}")
                                ret_val[name] = val
                    return ret_val

                from .back_end import get_reserved_names
                for (port_name, port_object) in ports(type(self._true_module)).items():
                    if port_name in get_reserved_names():
                        raise SyntaxErrorException(f"Class {self} uses reserved name as port definition {port_name}")
                    if port_object.has_source():
                        raise SyntaxErrorException(f"Class {self} has a port definition {port_name} with source already bound")
                    if len(port_object.sinks) != 0:
                        raise SyntaxErrorException(f"Class {self} has a port definition {port_name} with sinks already bound")
                    if port_object.get_parent_module() is not None:
                        raise SyntaxErrorException(f"Class {self} has a port definition {port_name} with parent module already assigned")
                    instance_port: Port = deepcopy(port_object)
                    # We need to use deepcopy to get all the important
                    # members, such as source/sinks/etc. objects
                    # de-duplicated. However we don't want to create
                    # a bunch of duplicate types, so override the reference
                    # to the newly created net_type
                    del instance_port._net_type
                    instance_port._net_type = port_object._net_type
                    instance_port.set_parent_module(self._true_module)
                    # Since we didn't actually create a new Port object - we've copied it, it's __init__ didn't get called.
                    # As such, some of the initialization didn't happen. Let's fix that
                    instance_port._init_phase2(self._true_module)
                    setattr(self._true_module, port_name, instance_port)

                    #print("Creating instance port with name: {} and type {}".format(port_name, port_object))
                #print("module {} is created".format(type(self)))
                # Store construct arguments locally so we can compare them later for is_equivalent
                (self._construct_args, self._construct_kwargs) = fill_arg_names(self._true_module.construct, args, kwargs)
                with self.netlist.set_current_scope(self._true_module):
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
            Context.register(self._context_change)

        def _context_change(self, context: Context) -> None:
            # Called by Context every time there's a change in context
            if context == Context.construction:
                self.setattr__impl = self._setattr__normal
            elif context == Context.elaboration:
                self.setattr__impl = self._setattr__normal
            elif context == Context.generation:
                self.setattr__impl = self._setattr__normal
            elif context == Context.simulation:
                self.setattr__impl = self._setattr__simulation
            else:
                self.setattr__impl = self._setattr__normal

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
                # 1. There is a sub-module, whose output is bound to a typed junction within this module.
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
        def get_local_wires(self) -> Sequence[Wire]:
            return self._local_wires.values
        def get_junctions(self) -> Sequence[Junction]:
            return chain(self._junctions.values(), self._local_wires.values())
        def get_fully_qualified_name(self) -> str:
            from .utils import FQN_DELIMITER
            node = self
            name = self.get_name()
            assert name is not None, f"Node {self} somehow doesn't have a name. Maybe didn't elaborate???"
            while node.parent is not None:
                node = node.parent._impl
                name = node.get_name() + FQN_DELIMITER + name
            return name
        def get_diagnostic_name(self, add_location: bool = True, add_type: bool = True, add_hierarchy: bool = True) -> str:
            from .utils import FQN_DELIMITER
            node = self
            names = self.netlist.symbol_table[self.parent].get_names(self._true_module)
            if len(names) == 0:
                if not add_type:
                    name = f"<unnamed:{type(self).__name__}>"
                else:
                    name = f"<unnamed>"
            else:
                name = first(names)
            if add_hierarchy:
                while node.parent is not None:
                    node = node.parent._impl
                    name = node.get_diagnostic_name(False, False, False) + (FQN_DELIMITER + name if name is not None else "")
            if add_location:
                name += self.get_diagnostic_location(" at ")
            if add_type:
                name = type(self._true_module).__name__ + " instance " + name
            return name

        def get_diagnostic_location(self, prefix: str = "") -> str:
            lineno = f":{self._lineno}" if self._lineno is not None else ""
            if self._filename is not None:
                return f"{prefix}{self._filename}{lineno}"

        def _set_no_bind_attr(self, name, value) -> None:
            # If we happen to override an existing Junction object, make sure it gets removed from port lists and the symbol table as well
            if name in self._true_module.__dict__ and self._true_module.__dict__[name] is value:
                assert False
            if name in self._true_module.__dict__:
                old_attr = self._true_module.__dict__[name]
                if is_junction_base(old_attr):
                    if is_port(junction):
                        old_attr.del_interface_name(name)
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
            # If we insert a new Junction object, update the port lists and the symbol table as well
            if is_junction_base(value):
                from .back_end import get_reserved_names
                if name in get_reserved_names():
                    raise SyntaxErrorException(f"Class {self} uses reserved name as wire definition {name}")
                junction = value
                junction.set_parent_module(self._true_module)
                assert junction.is_instantiable()
                self._junctions[name] = junction
                if is_port(junction):
                    junction.add_interface_name(name)
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
                    # Wires get thrown in _local_wires by their constructor.
                    # If they are later assigned to an attribute, let's remove them from the _local_wires collection.
                    try:
                        del self._local_wires[id(junction)]
                    except KeyError:
                        raise SyntaxErrorException(f"Can't add wire {junction} to module. Only wires created within the body of the same module can be added.")
                else:
                    assert False, "Unknown junction object kind {}".format(type(value))
                value.set_parent_module(self._true_module)
            # Finally set the actual attribute
            self.supersetattr(name, value)
        
        def register_wire(self, wire: Wire) -> None:
            assert id(wire) not in self._local_wires
            self._local_wires[id(wire)] = wire

        def _setattr__construction(self, name, value) -> None:
            """
            Called during the 'construct' call of an object.

            Here we allow creation of ports. In fact, we *assume* that you intend to create ports.
            We don't even allow binding of ports at this stage. That is to say: 'value' must not have a parent.
            """
            try:
                parent_module = value.get_parent_module()
                if parent_module not in (self._true_module, None):
                    raise SyntaxErrorException(f"Port '{name}' binding to '{value}' is not allowed in construction phase for module {self._true_module}")
            except AttributeError:
                pass
            return self._set_no_bind_attr(name, value)

        def _setattr__elaboration(self, name, value) -> None:
            """
            Called during the 'body' call of an object.

            Here we don't allow the creation of ports, but allow binding (<<=).
            If the port doesn't exist - and can't be created - we'll add it as
            a plane-old attribute. This means that the port (likely a sub-module port)
            is exposed on the module, but is not registered as an actual port.

            NOTE: since we only allow binding, port-creation will happen in the __get_attr__ call.

            TODO: we will need to make sure that the appropriate name gets registered
            and a wire is created as needed, similarly to what tracer does.
            """
            if name in self.get_ports().keys():
                raise SyntaxErrorException(f"Can't assign to existing port '{name}' on module '{self._true_module}'. Use the '<<=' operator instead.")
            if is_wire(value):
                self._set_no_bind_attr(name, value)
                return
            self.supersetattr(name, value)

        def _setattr__generation(self, name, value) -> None:
            """
            Called during the 'generate' call of an object.
            """
            self._setattr__elaboration(name, value)

        def _setattr__simulation(self, name, value) -> None:
            """
            Called during the 'simulation' call of an object.
            """
            self._setattr__elaboration(name, value)

            #if name in self.__dict__ and self.__dict__[name] is value:
            #    return
            #else:
            #    # For speedup reasons, removed is_junction_base calls, replaced tests with exceptions
            #    try:
            #        junction = self._true_module.__dict__[name]
            #    except KeyError:
            #        return self._set_no_bind_attr(name, value)
            #    try:
            #        if junction is not value:
            #            junction._set_sim_val(value)
            #    except AttributeError:
            #        return self._set_no_bind_attr(name, value)
            #    '''
            #    if name in self._true_module.__dict__ and is_junction_base(self._true_module.__dict__[name]):
            #        if port is not value:
            #            port._set_sim_val(value)
            #    else:
            #        return self._set_no_bind_attr(name, value)
            #    '''

        def _setattr__normal(self, name, value) -> None:
            """
            Called whenever we're not in any particular special situation.

            We don't allow port creation
            """
            if name not in self._true_module.__dict__:
                raise SyntaxErrorException(f"Silicon doesn't allow the creation of attributes on Modules at this point. Please set a default value to attribute '{name}' in 'construct'")
            if name in self.get_ports().keys():
                raise SyntaxErrorException(f"Silicon doesn't allow changing port {name} on module {self.get_diagnostic_name()} at this point. If you intend to bind to this port, use the '<<=' operator.")
            self.supersetattr(name, value)

            # This gets called whether the attribute 'name' exists or not.
            # TODO: we shouldn't allow port creation at all after 'construct'. All members set as junctions afterwards
            #       must be wires. In fact, what we should du inside 'body' is to create and add a wire every time we see this:
            #         self.boo = bah
            #       provided boo doesn't exist. If it does and it's a port, we should reject it.
            #       Otherwise the behavior should be identical to:
            #         boo = bah
            #       which BTW means that the tracer should also be reviewed.
            #       If both self.boo and boo exists, self.boo takes priority and boo becomes boo1 or something.
            #       Also, local boo should never be promoted to self.boo, even though it exists in Module.Impl.wires.
            ##with ScopedAttr(self, "_no_port_create_in_get_attr", True):
            ##    if name in self._true_module.__dict__ and self._true_module.__dict__[name] is value:
            ##        return
            ##    if name in self.get_ports().keys():
            ##        raise SyntaxErrorException(f"Can't assign to existing port {name} on module {self._true_module}. Use the '<<=' operator instead.")
            ##    if is_junction_base(value):
            ##        if value.get_parent_module() not in (self._true_module, None):
            ##            # We get here for the following code:
            ##            #   self.local_wire = Select(...)
            ##            # that is: we are trying to create a new wire for the output of the Select sub-module
            ##            wire = Wire()
            ##            self._set_no_bind_attr(name, wire)
            ##            wire <<= value
            ##            return
            ##    return self._set_no_bind_attr(name, value)

        def _create_named_port(self, name: str, *, port_type: Optional[Callable] = None, net_type: Optional[NetType] = None) -> Port:
            if self.is_interface_frozen():
                raise InvalidPortError
            port = self._true_module.create_named_port_callback(name, net_type)
            if port is None and port_type is not None:
                port = port_type()
            if port is None:
                raise InvalidPortError
            if not is_port(port):
                raise SyntaxErrorException("create_named_port_callback should return a 'Port' instance")
            self._set_no_bind_attr(name, port)
            return port

        def freeze_interface(self) -> None:
            self._frozen_port_list = True
        def is_interface_frozen(self) -> bool:
            return self._frozen_port_list
        def get_auto_port_to_bind(self,port_name_list) -> Optional[Port]:
            """
            Returns a port to bind an auto-port to, if a candidate exists or None if it doesn't
            """
            for name in port_name_list:
                if name in self._parent_local_junctions:
                    return convert_to_junction(self._parent_local_junctions[name])
            if self.parent is not None:
                parent_ports = self.parent.get_ports()
                for name in port_name_list:
                    if name in parent_ports:
                        return convert_to_junction(parent_ports[name])
                parent_wires = self.parent.get_wires()
                for name in port_name_list:
                    if name in parent_wires:
                        return convert_to_junction(parent_wires[name])
            return None

        def get_all_junctions(self) -> Sequence[Junction]:
            """
            Returns all junctions that are in the scope of this module.
            
            This includes ports and wires of the module itself, plus all the ports of all sub-modules
            """
            return chain(
                self.get_junctions(),
                chain(*(sub_module.get_inputs().values() for sub_module in self._sub_modules))
            )

        def _elaborate(self, trace: bool) -> None:
            # Recursively go through each new node, add it to the netlist and call its body (which most likely will create more new nodes).
            # The algorithm does a depth-first walk of the netlist hierarchy, eventually resulting in the full network and netlist created
            self.freeze_interface()
            if len(self._wires) != 0:
                raise SyntaxErrorException("A module can only have Inputs and Outputs before it's body gets called")

            assert len(self._local_wires) == 0

            # Let's call 'body' which will create all the sub-modules
            with ScopedAttr(self, "setattr__impl", self._setattr__elaboration):
                with self.netlist.set_current_scope(self._true_module):
                    with Module.Context(self):
                        old_attr_list = set(dir(self._true_module))
                        if trace:
                            with Tracer():
                                self._true_module.body()
                        else:
                            self._true_module.body()
                        # Look through all the attributes and register them, if needed.
                        for attr_name in dir(self._true_module):
                            if attr_name in old_attr_list:
                                continue
                            attr_value = getattr(self._true_module, attr_name)
                            if is_junction_base(attr_value):
                                register_local_wire(attr_name, attr_value, self._true_module, explicit=False, debug_print_level=0, debug_scope=f"{self}")

                    # Finish ordering sub-modules:
                    for sub_module in self._unordered_sub_modules:
                        self._sub_modules.append(sub_module)
                    del self._unordered_sub_modules # This will force all subsequent module instantiations (during type-propagation) to directly go to _sub_modules

                    # Go through each junction and make resolve their sources if needed
                    #   This is where we create PhiSlice objects for partial assignments for instance.
                    for junction in self.get_junctions():
                        junction.resolve_multiple_sources(self._true_module)

            for sub_module in self._sub_modules:
                # handle any pending auto-binds
                for port in sub_module.get_ports().values():
                    if port._auto:
                        port.auto_bind(self._true_module) # If already bound, this is a no-op, so it's safe to call it multiple times

            remaining_local_wires = dict()
            for wire in self._local_wires.values():
                if len(wire.sinks) == 0 and not wire.has_source():
                    print(f"WARNING: deleting unused local wire: {wire}")
                else:
                    remaining_local_wires[id(wire)] = wire
            self._local_wires = remaining_local_wires

            # Go through each sub-module in a loop, and finalize their interface until everything every Input port type is known

            def propagate_net_types():
                # First set net types on junctions where the source has a type, but the sink doesn't
                #incomplete_junctions = set(junction for junction in chain(self.get_junctions()) if not junction.is_specialized() and junction.has_source())
                incomplete_junctions = set(junction for junction in self.get_all_junctions() if not junction.is_specialized() and junction.has_source(allow_partials=False))
                changes = True
                while len(incomplete_junctions) > 0 and changes:
                    changes = False
                    for junction in tuple(incomplete_junctions):
                        source = junction.get_source()
                        if source.is_specialized():
                            junction.set_net_type(source.get_net_type())
                            changes = True
                            incomplete_junctions.remove(junction)
                # Look through all junctions for incompatible source-sink types and insert adaptors as needed
                for junction in tuple(self.get_all_junctions()):
                    old_source = junction.get_source()
                    if junction.is_specialized() and old_source is not None and old_source.is_specialized():
                        if junction.get_net_type() is not old_source.get_net_type():
                            # Inserting an adaptor
                            scope = junction.source_scope
                            with self.netlist.set_current_scope(scope):
                                source = implicit_adapt(old_source, junction.get_net_type())
                                # If an adaptor was created, fix up connectivity, including inserting a naming wire, if needed
                                if source is not old_source:
                                    parent_module = old_source.get_parent_module()
                                    names = self.netlist.symbol_table[parent_module._impl.parent].get_names(old_source)
                                    if len(names) > 0:
                                        name = names[0]
                                        naming_wire = Wire(source.get_net_type(), scope)
                                        self.netlist.symbol_table[scope].add_soft_symbol(naming_wire, name) # This creates duplicates of course, but that will be resolved later on
                                        naming_wire.set_source(source, scope=scope)
                                        junction.set_source(naming_wire, scope)
                                    else:
                                        junction.set_source(source, scope)

            with self.netlist.set_current_scope(self._true_module):
                incomplete_sub_modules = OrderedSet(self._sub_modules)
                changes = True
                while len(incomplete_sub_modules) > 0 and changes:
                    # Propagate types around on this hierarchy level until we can't do anything more.
                    propagate_net_types()

                    changes = False
                    for sub_module in tuple(incomplete_sub_modules):
                        all_inputs_specialized = all(tuple(input.is_specialized() or not input.has_driver() for input in sub_module.get_inputs().values()))
                        if all_inputs_specialized:
                            with Module.Context(sub_module._impl):
                                sub_module._impl._elaborate(trace)
                            changes = True
                            incomplete_sub_modules.remove(sub_module)
                # The elaboration of the final sub-module probably assigned some output net types, so propagate those around
                propagate_net_types()

            # If there were some sub-modules that we couldn't elaborate, that means we have some net types we can't determine.
            # Generate a fancy error message and bail.
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

            # The guts of the module is now complete. Let's make sure our outputs are in order as well.
            for output in self.get_outputs().values():
                if not output.is_specialized():
                    raise SyntaxErrorException(f"Output port {output} is not fully specialized after body call. Can't finalize interface")
            assert all((output.is_specialized() or not output.has_source()) for output in self.get_outputs().values())

        def is_top_level(self) -> bool:
            return self.netlist.top_level is self._true_module

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
                if type(my_junction.get_underlying_junction()) is not type(other_junction.get_underlying_junction()):
                    return False
                if my_junction.is_specialized() != other_junction.is_specialized():
                    return False
                if not my_junction.is_specialized():
                    return True
                return my_junction.get_net_type() is other_junction.get_net_type()

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
            with ScopedAttr(NetTypeMeta, "eq_is_is", True):
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

        def get_name(self) -> Optional[str]:
            names = self.netlist.symbol_table[self.parent].get_names(self._true_module)
            if len(names) == 0:
                return None
            if len(names) == 1:
                return first(names)
            assert False

        def populate_xnet_names(self, netlist: 'Netlist') -> None:
            """
            Makes sure that every xnet within the modules body have at least one name.

            At this point, all junction names are populated and made unique.
            
            TODO: I'm not sure if this should happen before or after braking up composites.
                  If it happens before, that means that new XNets (and names) will be created
                  and as a consequence, there could be new name-collisions.
            """

            # Start with all our own ports (must have at least one inner name)
            for my_port_name, my_port in self.get_ports().items():
                xnets = netlist.get_xnets_for_junction(my_port, my_port_name)
                for name, (xnet, port) in xnets.items():
                    xnet.add_name(self._true_module, name, is_explicit=True, is_input=is_input_port(port))
            # Look at named wires. These also have a name.
            for my_wire_name, my_wire in self.get_wires().items():
                xnets = netlist.get_xnets_for_junction(my_wire, my_wire_name)
                for name, (xnet, wire) in xnets.items():
                    xnet.add_name(self._true_module, name, is_explicit=True, is_input=False)

            # Look through local wires (Wire objects defined in the body of the module)
            # 1. promote them to the _wire map as well as make sure they're unique
            # 2. Add them to the associated xnet
            # 3. Give them a name if they're not named (for example, if they're part of a container such as a list or tuple)
            for my_wire in tuple(self._local_wires.values()):
                wire_name = first(netlist.symbol_table[self._true_module].get_names(my_wire))
                explicit = not netlist.symbol_table[self._true_module].is_auto_symbol(my_wire)
                # Get all the sub-nets (or the net itself if it's not a composite)
                # and handle those instead of my_wire.
                xnets = netlist.get_xnets_for_junction(my_wire, wire_name)
                for name, (xnet, wire) in xnets.items():
                    # Test if name is already registered as either my_wire or xnet
                    # If it is, make sure that it is the same object.
                    # Either way, make sure the xnet is aware of that name.
                    xnet.add_name(self._true_module, name, is_explicit=explicit, is_input=False)
                    self._wires[name] = wire
                    self._junctions[name] = wire
                del self._local_wires[id(my_wire)]
            assert len(self._local_wires) == 0

            # Finally, look through sub-module ports again, and check that all of them has at least one name
            # in their associated xnet for this scope. If not, create one.
            # NOTE: we broke this out from the previous loop to make the results stable and not depend
            #       on visitation order
            # NOTE: we only do this for outputs. The rationale is this: if there is an unconnected input
            #       on a sub-module, that net doesn't really exist in this scope. If the input *is* connected,
            #       even if we don't iterate through it here, we would eventually come across it's driving output.
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
                            if source_module is self._true_module:
                                name = first(source_port.get_interface_names())
                            else:
                                name = f"{source_module._impl.get_name()}{MEMBER_DELIMITER}{first(source_port.get_interface_names())}"
                            xnet.add_name(self._true_module, name, is_explicit=False, is_input=False) # These ports are not inputs, at least not as far is this context is concerned.


        def _generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> Optional[str]:
            if not self._generate_needed:
                return None
            with ScopedAttr(self, "setattr__impl", self._setattr__generation):
                return self._true_module.generate(netlist, back_end)


class GenericModule(Module):
    def __new__(cls, *args, **kwargs):
        # A generic class will always pass all its arguments to __init__.
        return super().__new__(cls)

class DecoratorModule(GenericModule):
    def construct(self, function: Callable, out_port_cnt: int) -> None:
        self._allow_port_creation = False

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

    def create_named_port_callback(self, name: str, net_type: Optional['NetType'] = None) -> Optional[Port]:
        if not self._allow_port_creation:
            raise InvalidPortError()
        return Input(net_type)

    @no_trace
    def body(self) -> None:
        return_values = self._impl.function(*self._impl._args, **self._impl._kwargs)
        if isinstance(return_values, str) or is_junction_base(return_values) or not is_iterable(return_values):
            return_values = (return_values, )
        if len(return_values) != len(self._impl.get_outputs()):
            raise SyntaxErrorException(f"Modularized function returned {len(return_values)} values, where decorator declared {len(self._impl.get_outputs())} outputs. These two must match")
        for return_value, (name, output_port) in zip(return_values, self._impl.get_outputs().items()):
            assert not output_port.has_source()
            try:
                output_port <<= return_value
            except SyntaxErrorException:
                raise SyntaxErrorException(f"Modularized function must return output ports or at least things that can be turned into output ports")

    def __call__(self, *args, **kwargs) -> Union[Port, Tuple[Port]]:
        # For any port argument, we'll create an input port (yet unnamed and not added to the interface)
        # For all other arguments, we simply pass them on as-is
        self._impl._kwargs = dict()
        scope = self._impl.parent
        # Named arguments are easy: we know what to bind them to and we know their name as well, so we need no magic
        for name, arg in kwargs.items():
            if scope is None:
                raise SyntaxErrorException("Can't instantiate top level module with call-syntax and port-bindings") 
            if is_junction_base(arg):
                with ScopedAttr(self, "_allow_port_creation", True):
                    my_arg = self.create_named_port(name)
                my_arg.set_source(arg, scope)
            else:
                my_arg = arg
            self._impl._kwargs[name] = my_arg

        # This is a bit tricky here:
        # We need to create ports for all of by positional arguments, or at least the ones that are ports.
        # We will end up storing all of them (port so otherwise) in self._impl._args so that we can
        # pass then to the actual function that defines the module once we're in 'body()'.
        # However, in order to get the right port names for positional arguments, we'll have to
        # bind them to the actual signature of the implementation function. What's even more complicated
        # is that we can't really create the port before such binding, because we don't know its name.
        # So, what we'll do here is to create placeholder objects for each port that we intend to create
        # and put them into a map to their actual arguments. Then we mock-bind them all (placeholders and others)
        # to the signature. Finally, we'll go through the binding results, extract our placeholders, create
        # the real ports (now we have names), hook them up to the incoming arguments, and replace them in
        # self._impl._args.
        # All of this logic will fail if the underlying function also has *args or **kwargs arguments. In those
        # cases we won't be able to create nice names for positional argument ports, so we'll just create
        # some name and move on.
        self._impl._args = []
        ports_needing_name = set()
        arg_to_port_map = {}
        for idx, arg in enumerate(args):

            class PlaceHolder(object):
                def __init__(self, arg, idx):
                    self.arg = arg
                    self.idx = idx

            if scope is None:
                raise SyntaxErrorException("Can't instantiate top level module with call-syntax and port-bindings") 
            if is_junction_base(arg):
                placeholder = PlaceHolder(arg, idx)
                ports_needing_name.add(placeholder)
                my_arg = placeholder
            else:
                my_arg = arg
            self._impl._args.append(my_arg)
        # mock-bind the now created invocation arguments to the signature of the function
        # and attempt to locate the ports that need a name. This might fail if 'function' itself
        # has *args or **kwargs arguments
        from inspect import signature
        sig = signature(self._impl.function)
        bound_args = sig.bind(*self._impl._args, **self._impl._kwargs).arguments
        for name, my_arg in bound_args.items():
            if my_arg in ports_needing_name:
                with ScopedAttr(self, "_allow_port_creation", True):
                    port = self.create_named_port(name)
                port.set_source(my_arg.arg, scope) # Now that we have our port, we can bind it to the actual port, that's passed int
                self._impl._args[my_arg.idx] = port # replace the placeholder with the real port, now that we have it
                ports_needing_name.remove(my_arg)
        # Work through the remaining inputs and simply name them consecutively
        for idx, placeholder in enumerate(ports_needing_name):
            port_name = f"intput_{idx}"
            if name in self.__dict__:
                raise SyntaxErrorException("Can't add port {port_name} to modularized function: the attribute already exists")
            with ScopedAttr(self, "_allow_port_creation", True):
                port = self.create_named_port(port_name)
            port.set_source(placeholder.arg, scope)
            self._impl._args[placeholder.idx] = port

        # Check that we don't have any placeholders left
        assert not any(isinstance(arg, PlaceHolder) for arg in self._impl._args)

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

