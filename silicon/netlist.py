from typing import Union, Set, Tuple, Dict, Any, Optional, List, Iterable, NamedTuple, Sequence, Callable, Generator
import typing
from .ordered_set import OrderedSet
from collections import OrderedDict
from .port import is_port
from .port import Junction
from .utils import is_input_port, is_output_port, is_wire, is_module, MEMBER_DELIMITER, ContextMarker, Context
from .utils import vprint, verbose_enough, VerbosityLevels, profile
from itertools import chain
from .exceptions import SyntaxErrorException
from .stack import Stack
from pathlib import Path
from .sym_table import SymbolTable

def fully_qualified_name(thing: Any, mangle: bool=True) -> str:
    type = thing.__class__
    module = type.__module__
    if module == "__main__":
        # We need to work around the problem that Python names the main module '__main__', but
        # we would like to keep it consistent and use the file-name, if possible
        import __main__
        from pathlib import Path
        main_path = Path(__main__.__file__)
        module = main_path.stem
    if module == 'builtins':
        return type.__qualname__
    fqn: str = module + '.' + type.__qualname__
    if mangle:
        fqn = fqn.replace("__","")
        fqn = fqn.replace("<","_")
        fqn = fqn.replace(">","_")
        fqn = fqn.replace(".","_")
    return fqn
class XNet(object):
    class NameStatus(object):
        def __init__(self, *, is_explicit: bool = True, is_used: bool = False, is_input: bool = False):
            self.is_explicit = is_explicit
            self.is_used = is_used
            self.is_input = is_input

    def __init__(self):
        from .port import Port, Wire
        self._source: Junction = None
        self._sinks: Set[Port] = OrderedSet()
        self._transitions: Set[Port] = OrderedSet()
        self._aliases: Set[Wire] = OrderedSet()
        self.scoped_names: Dict['Module', Dict[str, 'XNet.NameStatus']] = OrderedDict()
        self.rhs_expressions: Dict['Module', Tuple[str, int]] = OrderedDict()
        self.assigned_names: Dict['Module', str] = OrderedDict()

    def add_source(self, junction: 'Junction') -> None:
        assert self._source is None
        self._source = junction

    def add_sink(self, junction: 'Junction') -> None:
        self._sinks.add(junction)

    def add_transition(self, junction: 'Junction') -> None:
        self._transitions.add(junction)

    def add_alias(self, junction: 'Junction') -> None:
        self._aliases.add(junction)

    def is_source(self, junction: 'Junction') -> bool:
        return junction is self._source

    def is_sink(self, junction: 'Junction') -> bool:
        return junction in self._sinks

    def is_transition(self, junction: 'Junction') -> bool:
        return junction in self._transitions

    def is_alias(self, junction: 'Junction') -> bool:
        return junction in self._aliases

    def get_source(self) -> Optional['Junction']:
        return self._source

    def num_junctions(self, *, include_source: bool) -> int:
        return len(self._sinks) + len(self._aliases) + len(self._transitions) + int(self._source is not None and include_source)

    def add_rhs_expression(self, scope: 'Module', expr: str, precedence: int, verilog_bit_width: Optional[int]) -> None:
        if verilog_bit_width is None:
            verilog_bit_width = self.get_num_bits()
        assert scope is None or is_module(scope)
        if scope not in self.rhs_expressions:
            self.rhs_expressions[scope] = (expr, precedence, verilog_bit_width)
        else:
            current = self.rhs_expressions[scope]
            assert current[0] == expr and current[1] == precedence and current[2] == verilog_bit_width

    def get_rhs_expression(self, scope: 'Module', back_end: 'BackEnd', allow_expression: bool = True) -> Tuple[str, int]:
        assert scope is None or is_module(scope)
        # We should return the unconnected value if there's no source for this XNet at all.
        if self._source is None:
            net_type = self.get_net_type()
            if net_type is None:
                raise SyntaxErrorException(f"Can't determine unconnected value for unconnected XNet")
            return net_type.get_unconnected_value(back_end), 0
        if scope in self.assigned_names:
            return self.assigned_names[scope], 0
        make_name_used = False
        if scope in self.rhs_expressions and allow_expression:
            # If the Verilog width is not the same as our width, that means that (depending on the context)
            # Verilog might not evaluate the expression at the right width. There are two ways to fix that.
            # 1. Add the right-sized 0 to the expression (i.e. a*b + 16'b0)
            # 2. Break the sub-expression out into it's own (i.e. logic [15:0] something; something = a*b;)
            # We will do #2 if a name exists, and #1 otherwise
            expr, precedence, verilog_bit_count = self.rhs_expressions[scope]
            if verilog_bit_count >= self.get_num_bits():
                return expr, precedence
            name = self.get_lhs_name(scope, allow_implicit=False, mark_assigned=True)
            if name is not None:
                return name, 0
            op_prec = back_end.get_operator_precedence("+", False)
            expr, _ = back_end.wrap_expression(expr, precedence, op_prec)
            expr = f"{expr} + {self.get_num_bits()}'b0"
            return expr, op_prec
        else:
            # We are going to return a name. We have to make sure that an eventual assignment to that name is made
            make_name_used = True
        # If we're asked to return the name in the source context, we should return the unconnected value.
        # That is because an XNet is either sourced by a primitive (which would never ask for the RHS name of its output)
        # or it's unconnected, in which case we should return the unconnected value.
        if scope == self._source.get_parent_module():
            name = None
        else:
            name = self.get_lhs_name(scope, allow_implicit=True, mark_assigned=False)
        if name is None:
            # We end up here with an unconnected input in the instantiation scope, if that input feeds other sub-module inputs within the instance.
            port = self._source
            if not port.is_specialized():
                return back_end.get_unconnected_value(), 0
            return port.get_net_type().get_unconnected_value(back_end), 0
        else:
            if make_name_used:
                self.use_name(scope, name)
            return name, 0 # This will put the returned value into self.assigned_names

    def get_lhs_name(self, scope: 'Module', *, allow_implicit: bool = True, mark_assigned: bool = True) -> Optional[str]:
        assert scope is None or is_module(scope)
        # If we are going to mark the name assigned, get a name that's not already is so.
        name = self.get_best_name(scope, allow_implicit=allow_implicit, exclude_assigned=mark_assigned)
        if name is not None and mark_assigned:
            self.assign_name(scope, name)
        return name
    def generate_assign(self, sink_name: str, source_expression: str, back_end: 'BackEnd') -> str:
        return self.get_net_type().generate_assign(sink_name, source_expression, self, back_end)
    def add_name(self, scope: 'Module', name: str, *, is_explicit: bool, is_input: bool) -> None:
        assert is_module(scope)
        if scope not in self.scoped_names:
            self.scoped_names[scope] = dict()
        # Only add implicit names if we don't already have an explicit one
        if len(self.scoped_names[scope]) == 0 or is_explicit:
            self.scoped_names[scope][name] = XNet.NameStatus(is_explicit = is_explicit, is_input = is_input)
    def use_name(self, scope: 'Module', name: str) -> None:
        assert is_module(scope)
        self.scoped_names[scope][name].is_used = True
    def assign_name(self, scope: 'Module', name: str) -> None:
        assert is_module(scope)
        # It's actually possible that we have multiple names assigned in a scope.
        # This happens if multiple inputs to the Module are driven by the same source.
        # While it could be filtered for outside (in Moudle.Impl.generate), it's easier
        # to simply not check for it here and keep the first assigned name if multiple
        # exist.
        #assert scope not in self.assigned_names or self.assigned_names[scope] == name
        if scope not in self.assigned_names:
            self.assigned_names[scope] = name

    def get_names(self, scope: 'Module') -> Optional[Sequence[str]]:
        assert scope is None or is_module(scope)
        if scope not in self.scoped_names:
            return None
        names = tuple(self.scoped_names[scope].keys())
        if len(names) == 0:
            return None
        return names

    def _get_filtered_names(self, scope: 'Module', filter_fn: Callable):
        assert scope is None or is_module(scope)
        if scope not in self.scoped_names:
            return None
        names = tuple(elem[0] for elem in (filter(filter_fn, self.scoped_names[scope].items())))
        if len(names) == 0:
            return None
        return names

    def get_explicit_names(self, scope: 'Module', *, add_used: bool, add_assigned: bool, exclude_assigned: bool) -> Optional[Sequence[str]]:
        assert scope is None or is_module(scope)
        def do_filter(entry) -> bool:
            return (
                not entry[1].is_input and (
                    ((entry[1].is_explicit or (add_used and entry[1].is_used)) and (not exclude_assigned or entry[0] != self.assigned_names.get(scope, None))) or
                    ((add_assigned and not exclude_assigned) and (entry[0] == self.assigned_names.get(scope, None)))
                )
            )
        return self._get_filtered_names(scope, do_filter)

    def get_used_names(self, scope: 'Module', *, add_implicit: bool = True) -> Optional[Sequence[str]]:
        assert scope is None or is_module(scope)
        def do_filter(entry) -> bool:
            return entry[1].is_used and (entry[1].is_explicit or add_implicit)
        return self._get_filtered_names(scope, do_filter)

    def get_used_or_assigned_names(self, scope: 'Module', *, add_implicit: bool = True) -> Optional[Sequence[str]]:
        assert scope is None or is_module(scope)
        def do_filter(entry) -> bool:
            return ((entry[0] == self.assigned_names.get(scope, None)) or entry[1].is_used) and (entry[1].is_explicit or add_implicit)
        return self._get_filtered_names(scope, do_filter)

    def get_best_name(self, scope: 'Module', *, allow_implicit: bool = True, exclude_assigned: bool = False) -> Optional[str]:
        assert scope is None or is_module(scope)
        if scope in self.assigned_names and not exclude_assigned:
            return self.assigned_names[scope]
        best_name = None
        best_status = XNet.NameStatus(is_explicit=False)
        if scope in self.scoped_names:
            for name, status in self.scoped_names[scope].items():
                if status.is_used and not best_status.is_used:
                    best_status = status
                    best_name = name
                elif status.is_explicit and not best_status.is_explicit:
                    best_status = status
                    best_name = name
                else:
                    best_status = status
                    best_name = name
        if not allow_implicit and not best_status.is_explicit:
            return None
        # It's possible that even the best name for this XNet is 'None' within an interesting scope.
        # Imagine an input port in the instantiation scope that is left unconnected.
        # This XNet actually 'lives' in the instantiation scope, yet there's no way to reference it,
        # so it has no 'best' name
        #assert best_name is not None, "An XNet should have at least one name in every interesting scope"
        return best_name


    def get_diagnostic_name(self, netlist: 'Netlist') -> str:
        def get_fully_qualified_names(xnet, add_unnamed_scopes: bool) -> Generator[str, None, None]:
            from .utils import FQN_DELIMITER
            for scope in xnet.scoped_names.keys():
                module_name = scope._impl.get_fully_qualified_name()
                if not netlist.symbol_table[scope._impl.parent].is_auto_symbol(scope) or add_unnamed_scopes:
                    names_in_scope = xnet.get_names(scope)
                    for name in names_in_scope:
                        yield module_name + FQN_DELIMITER + name

        fqn = tuple(get_fully_qualified_names(self, False))
        if len(fqn) == 0:
            fqn = tuple(get_fully_qualified_names(self, True))
        if len(fqn) == 0:
            return f"UNNAMED XNET {id(self):x}"
        return ' a.k.a. '.join(fqn)

    def get_net_type(self) -> 'NetType':
        if self._source is not None:
            return self._source.get_net_type()
        for port in self._transitions:
            return port.get_net_type()
        for sink in self._sinks:
            return sink.get_net_type()
        for alias in self._aliases:
            return alias.get_net_type()
        assert False

    @property
    def sim_value(self) -> Any:
        return self.sim_state.value

    def get_num_bits(self) -> int:
        return self.get_net_type().get_num_bits()

class Netlist(object):
    def __init__(self):
        self.top_level = None
        self.modules: Set['Module'] = OrderedSet()
        self.net_types: Dict[str, List['NetType']]= OrderedDict()
        self.ports: Set[object] = OrderedSet()
        self.simulator_context: Optional['Simulator.SimulatorContext'] = None
        self.module_variants: Optional[Dict[str, Dict[str, List['Module']]]] = None
        self.module_to_class_map: Optional[Dict['Module', str]] = None
        self.module_class_short_name_map: Dict[str, str] = OrderedDict() # Maps short names to their fully qualified names
        self.xnets: Set[XNet] = OrderedSet()
        self.junction_to_xnet_map = OrderedDict()
        self.module_to_xnet_map = OrderedDict()
        self._parent_modules = Stack()
        self.enter_depth = 0
        self.symbol_table = SymbolTable()
        self.rank_list = None
        self.rank_map = None

    @staticmethod
    def get_global_netlist() -> 'Netlist':
        return globals()["netlist"]

    def get_current_scope(self = None) -> Optional['Module']:
        """
        Returns the current scope module, or None if no scope is set.
        """
        if self is None:
            try:
                return globals()["netlist"].get_current_scope()
            except KeyError:
                return None
        if self._parent_modules.is_empty():
            return None
        return self._parent_modules.top()

    def set_current_scope(self, module: 'Module') -> Stack.Context:
        """
        Sets the current scope to 'module'.

        Returns an context manager that can be used in a 'with' block to control the lifetime of the scope safely.
        """
        return self._parent_modules.push(module)

    def __enter__(self) -> 'Netlist':
        if "netlist" in globals():
            if globals()["netlist"] is not self:
                raise SyntaxErrorException("There can be only one active Netlist")
        globals()["netlist"] = self
        self.enter_depth += 1
        return self
    def __exit__(self, exception_type, exception_value, traceback):
        if self.enter_depth == 1:
            del globals()["netlist"]
        self.enter_depth -= 1

    #def __getstate__(self):
    #    state = self.__dict__.copy()
    #    del state["top_level"]
    #    del state["modules"]
    #    del state["net_types"]
    #    del state["ports"]
    #    del state["simulator_context"]
    #    del state["module_variants"]
    #    del state["module_to_class_map"]
    #    del state["module_class_short_name_map"]
    #    del state["xnets"]
    #    del state["junction_to_xnet_map"]
    #    del state["module_to_xnet_map"]
    #    del state["_parent_modules"]
    #    del state["enter_depth"]
    #    del state["symbol_table"]
    #    del state["rank_list"]
    #    del state["rank_map"]
    #    return state
    #
    #def __setstate__(self, state):
    #    self.__dict__.update(state)
    #    # TODO: restore everything...

    def _register_net_type(self, net_type: 'NetType'):
        type_name = net_type.get_type_name()
        if type_name is not None:
            if type_name not in self.net_types:
                self.net_types[type_name] = []
            self.net_types[type_name].append(net_type)
    def _register_junction(self, junction: 'Junction'):
        # Note: we register only the junctions' type and its NetType, not the junction object itself.
        # NetType is needed for types that need generation (enums, structs, interfaces etc.)
        # The type of the port is needed to be able to 'reverse' port directions for things, such as interfaces
        if junction.is_specialized():
            self._register_net_type(junction.get_net_type()) # This is the actual data type carried over the port, such as Logic or a Vector of something...
        if is_port(junction):
            self.ports.add(type(junction)) # This would be 'Input' or 'Output' for most cases

    def _create_xnets(self):
        """
        Creates XNet objects for the netlist.

        XNets are nets that span hierarchy. They collect all ports that share the same source,
        even if they go through multiple hierarchy levels. Wires, sharing the same source
        are also inserted into the XNet.

        These XNet objects can be used to quickly determine 'sphere of influence' for any
        source port, which helps with simulation.
        """

        def create_xnets_for_junction(for_junction: 'Junction') -> Sequence[XNet]:
            if for_junction.is_composite():
                xnets = []
                for member_junction, _ in for_junction.get_member_junctions().values():
                    xnets += create_xnets_for_junction(member_junction)
                return xnets
            else:
                if for_junction.has_source():
                    # Only create XNets for things that source something. Sinks will get added to existing XNets once the source is identified.
                    return []
                else:
                    x_net = XNet()

                    def trace_x_net(current_junction: Junction):
                        for sink in current_junction.get_sinks():
                            if is_wire(sink):
                                x_net.add_alias(sink)
                            else:
                                if not sink.has_sinks():
                                    # No sinks of this junction: this is a terminal node.
                                    x_net.add_sink(sink)
                                else:
                                    x_net.add_transition(sink)
                            self.junction_to_xnet_map[sink] = x_net
                            sink._xnet = x_net
                            trace_x_net(sink)

                    self.junction_to_xnet_map[for_junction] = x_net
                    for_junction._xnet = x_net
                    trace_x_net(for_junction)

                    if x_net.num_junctions(include_source=True) == 0:
                        # XNet contains only this single junction --> Determine if it's a source-only XNet or a source-less one
                        if is_wire(for_junction):
                            x_net.add_alias(for_junction)
                        elif is_input_port(for_junction):
                            # This is an XNet with a single input on it. That is: it's an unconnected input.
                            x_net.add_transition(for_junction)
                            #x_net.add_source(for_junction)
                        else:
                            assert is_output_port(for_junction)
                            # This is difficult: An output can be unconnected because no one drives it or because
                            # it drives no one. If no one drives it, that doesn't mean it can't be a source from
                            # a primitive, that'll eventually assign (simulation) values to it.
                            # Of course that doesn't matter all that much in the grand scheme of things as there's
                            # no one listening to those value changes.
                            # Since we can't determine which of the two cases it is, we'll list this output as a sink
                            # and will make special accommodations in the simulator so that the values are dumped as
                            # needed
                            x_net.add_sink(for_junction)
                    else:
                        x_net.add_source(for_junction)
                    return [x_net]

        for module in self.modules:
            for junction in chain(module.get_junctions()):
                self.xnets |= create_xnets_for_junction(junction)

        for module in self.modules:
            for port in module.get_ports().values():
                if port not in self.junction_to_xnet_map and not port.is_composite():
                    raise SyntaxErrorException(
                        f"Can't create XNet for port {port}.\n"\
                        "Possible reasons:\n"\
                        "    - Port is connected to itself somehow, creating a trivial combinatorial loop\n"\
                        "    - Port is driven by an unassigned junction\n"
                        "    - Port is driven by local wire that accidentally assigned to (=) instead of bound (<<=)"
                    )

    def _fill_xnet_names(self):
        # Fill-in names for xnets
        for xnet in self.xnets:
            from .utils import FQN_DELIMITER
            for scope in xnet.scoped_names.keys():
                if scope not in self.module_to_xnet_map:
                    self.module_to_xnet_map[scope] = OrderedSet()
                self.module_to_xnet_map[scope].add(xnet)
                module_name = scope._impl.get_fully_qualified_name()

    def _rank_netlist(self) -> Tuple[List[Set['Module']], Dict['Module', int]]:
        """
        Creates a DAG from the netlist (by forcing all non-combinational modules into rank 0)
        Arranges every module by rank in the DAG and returns the DAG

        NOTE: this can only be called after _create_xnets was called
        """
        from .module import Module
        rank_map: Dict[Module, int] = OrderedDict()
        rank_list: List[Set[Module]] = []
        xnet_trace: List[XNet] = []

        def get_sourced_xnets(module: Module) -> Set[XNet]:
            xnets = OrderedSet()
            for port in module.get_ports().values():
                xnet = self.junction_to_xnet_map[port]
                if xnet.is_source(port):
                    xnets.add(xnet)
            return xnets

        def get_sinked_xnets(module: Module) -> Set[XNet]:
            xnets = OrderedSet()
            for port in module.get_ports().values():
                for member in port.get_all_member_junctions(add_self=True):
                    if member.is_composite():
                        continue
                    xnet = self.junction_to_xnet_map[member]
                    if xnet.is_sink(member):
                        xnets.add(xnet)
            return xnets

        def _rank_module(module: Module, xnet: Optional[XNet] = None, iter_level: int = 0) -> int:
            assert module is not None
            if xnet is not None:
                xnet_trace.append(xnet)
            assert iter_level < 100
            if module in rank_map:
                if xnet is not None: xnet_trace.pop()
                return rank_map[module]
            # Check for loops (i.e. if graph truly is a DAG)
            if module in visited_modules:
                def xnet_trace_names():
                    return "\n    ".join(xnet.get_diagnostic_name(self) for xnet in xnet_trace)
                raise SyntaxErrorException(f"Combinational loop found:\n    {xnet_trace_names()}")
            visited_modules.add(module)
            if not module.is_combinational():
                rank = 0
            else:
                source_xnets = get_sinked_xnets(module)
                if len(source_xnets) == 0:
                    rank = 0
                else:
                    sources = OrderedSet((source_xnet.get_source(), source_xnet) for source_xnet in source_xnets if source_xnet.get_source() is not None)
                    source_modules = OrderedSet((source[0].get_parent_module(), source[1]) for source in sources if source[0].get_parent_module() is not None)
                    if len(source_modules) == 0:
                        rank = 0
                    else:
                        assert None not in source_modules
                        rank = max(_rank_module(source_module[0], source_module[1], iter_level + 1) + 1 for source_module in source_modules)
            rank_map[module] = rank
            while len(rank_list) <= rank:
                rank_list.append(OrderedSet())
            rank_list[rank].add(module)
            if xnet is not None: xnet_trace.pop()
            visited_modules.remove(module)
            return rank

        for module in self.modules:
            visited_modules = set()
            _rank_module(module)
        for module in self.modules:
            assert module in rank_map

        return rank_list, rank_map

    def get_xnet_for_junction(self, junction: 'Junction') -> 'XNet':
        if junction not in self.junction_to_xnet_map:
            raise SyntaxErrorException(f"Can't associate {junction} with any Xnet. Most likely reason is that it doesn't have a source.")
        return self.junction_to_xnet_map[junction]

    def get_xnets_for_junction(self, junction: 'Junction', base_name: str = "<unknown>") -> Dict[str, Tuple['XNet', 'Junction']]:
        """
        Return a set of XNets for a given junction. Normally, this is just a single XNet, but for composites, it's one XNet per member.
        """
        if not junction.is_composite():
            return {base_name: (self.get_xnet_for_junction(junction), junction)}
        ret_val = OrderedDict()
        for member_name, (member_junction, _) in junction.get_member_junctions().items():
            ret_val.update(self.get_xnets_for_junction(member_junction, f"{base_name}{MEMBER_DELIMITER}{member_name}"))
        return ret_val

    def get_xnets_for_module(self, module: 'Module') -> Set['XNet']:
        assert is_module(module)
        if module not in self.module_to_xnet_map:
            return set()
        return self.module_to_xnet_map[module]

    def get_module_class_name(self, module_instance: 'Module') -> Optional[str]:
        assert is_module(module_instance)
        if module_instance not in self.module_to_class_map:
            return None
        return self.module_to_class_map[module_instance]

    def register_module(self, module: 'Module'):
        assert is_module(module)
        if self.top_level is None:
            self.top_level = module
        self.modules.add(module)
        self.symbol_table[self.get_current_scope()].add_auto_symbol(module)

    def get_top_level_name(self) -> str:
        return self.get_module_class_name(self.top_level)

    class Elaborator(object):
        def __init__(self, netlist: 'Netlist'):
            self.netlist = netlist
        def __enter__(self):
            self.netlist.__enter__()
            self.marker = ContextMarker(Context.elaboration)
            self.marker.__enter__()
            return self.netlist
        def __exit__(self, exception_type, exception_value, traceback):
            try:
                if exception_type is None:
                    self.netlist._elaborate()
            finally:
                self.marker.__exit__(exception_type, exception_value, traceback)
                self.netlist.__exit__(exception_type, exception_value, traceback)

    def elaborate(self) -> 'Netlist.Elaborator':
        return Netlist.Elaborator(self)

    @profile
    def _elaborate(self) -> None:
        from .module import Module

        top_impl: Module.Impl = self.top_level._impl

        # Give top level a name and mark it as user-assigned.
        scope_table = self.symbol_table[None]
        if scope_table.is_auto_symbol(self.top_level):
            scope_table.add_hard_symbol(self.top_level, type(self.top_level).__name__)

        with Module.Context(top_impl):
            all_inputs_specialized = all(tuple(input.is_specialized() for input in top_impl.get_inputs().values()))
            if not all_inputs_specialized:
                raise SyntaxErrorException(f"Top level module must have all its inputs specialized before it can be elaborated")
            top_impl._elaborate(trace=True)

        # Deal with all the cleanup after elaboration.
        #
        # For now, it consists of:
        # - Generate module and net names
        # - Creation of XNets
        # - Ranking modules into logic cones
        # - Sorting all the modules into instance classes. That is, create a set of module instances who share the same implementation.
        #   This is a bit more complex then simply looking at their type or __class__: generic modules or modules with dynamic port creation
        #   support may not share the body even if they are of the same class.
        #   TODO: in fact, this shouldn't happen at all this way: it's way too brittle. I think a better way of dealing with this is to
        #         str-compare the generated guts after the fact and eject the identical ones.
        def populate_names(module: 'Module'):
            module._impl.populate_xnet_names(self)
            for sub_module in module._impl.get_sub_modules():
                populate_names(sub_module)

        def populate_module_variants(module: 'Module'):
            def _populate_module_variants(module: 'Module'):
                # First recurse into all sub-modules, then deal with this one...
                for sub_module in module._impl.get_sub_modules():
                    _populate_module_variants(sub_module)

                assert module not in self.module_to_class_map

                module_class_base_name = fully_qualified_name(module)
                module_class_short_name = module.__class__.__name__
                found = False
                if module_class_base_name not in self.module_variants:
                    self.module_variants[module_class_base_name] = OrderedDict()
                else:
                    for variant_name, variant_instances in self.module_variants[module_class_base_name].items():
                        # We assume that if we're compatible with one variant instance, we're compatible with all of them.
                        # Now, this is potentially a bit restrictive, but the alternative is an O(N^2) search, which would be bad (TM)
                        variant_instance = variant_instances[0]
                        if not module._impl.is_equivalent(variant_instance, self):
                            continue
                        variant_instances.append(module)
                        self.module_to_class_map[module] = variant_name
                        found = True
                        break
                if not found:
                    # We need to come up with a module class name
                    # Try to use the short name, but revert to the long one, if there's a collision
                    variant_cnt = len(self.module_variants[module_class_base_name])
                    module_class_name = module_class_short_name
                    if module_class_short_name not in self.module_class_short_name_map:
                        self.module_class_short_name_map[module_class_short_name] = module_class_base_name
                    else:
                        if self.module_class_short_name_map[module_class_short_name] != module_class_base_name:
                            module_class_name = module_class_base_name
                    if variant_cnt != 0:
                        module_class_name += "_" + str(variant_cnt+1)
                    self.module_variants[module_class_base_name][module_class_name] = [module]
                    self.module_to_class_map[module] = module_class_name

            _populate_module_variants(module)

        def lint_modules(module: 'Module'):
            assert module in self.modules
            assert module._impl.netlist is self
            for sub_module in module._impl.get_sub_modules():
                lint_modules(sub_module)

        lint_modules(self.top_level)
        for module in self.modules:
            for junction in module.get_junctions():
                self._register_junction(junction)
        self._create_xnets()

        def delimiter(obj: object) -> str:
            if is_module(obj):
                return ""
            return "_"

        for sub_module in module._impl._sub_modules:
            assert self.symbol_table[module].exists(sub_module)

        self.symbol_table.make_unique(delimiter)
        populate_names(self.top_level)
        self._fill_xnet_names()

        #for xnet in self.xnets:
        #    print(f"xnet {hex(id(xnet))} names: {'; '.join(tuple(' '.join(name.keys()) for name in xnet.scoped_names.values()))}")

        self.rank_list, self.rank_map = self._rank_netlist()
        self.module_variants = OrderedDict()
        self.module_to_class_map = OrderedDict()
        populate_module_variants(self.top_level)
        # Make sure we've got to everyone
        for module in self.modules:
            assert module in self.module_to_class_map

        def print_submodules(module: 'Module', level: int = 0) -> None:
            if verbose_enough(VerbosityLevels.instantiation):
                vprint(VerbosityLevels.instantiation, f"  {'  '*level}{module._impl.get_diagnostic_name()}")
                for sub_module in module._impl._sub_modules:
                    print_submodules(sub_module, level+1)
        vprint(VerbosityLevels.instantiation, "Module hierarchy:")
        print_submodules(self.top_level)

    @profile
    def generate(self, back_end: 'BackEnd', file_names: Optional[Union[str, Dict[type, str]]] = None) -> None:
        from .utils import str_block

        streams = back_end.generate_order(self, file_names)

        self.top_level._impl._generate_needed = True
        for stream, (modules, types) in streams.items():
            with stream as strm:
                type_impls = ""
                for net_type in types:
                    type_impl = net_type.generate(self, back_end)
                    if type_impl is not None and len(type_impl) > 0:
                        type_impls += str_block(type_impl, "", "\n\n")
                strm.write(str_block(type_impls, "/"*80+"\n// Type definitions\n"+"/"*80+"\n", "\n\n\n"))

                for module in reversed(modules):
                    module_impl = module._impl._generate(self, back_end)
                    if module_impl is not None:
                        strm.write(str_block(module_impl, "", "\n\n\n"))
                    # Mark all instances of the same variant as no body needed
                    module_class_base_name = fully_qualified_name(module)
                    module_class_name = self.module_to_class_map[module]
                    for module_inst in self.module_variants[module_class_base_name][module_class_name]:
                        module_inst._impl._generate_needed = False
                        module_inst._impl._body_generated = True

    def simulate(
        self,
        vcd_file_name: Union[Path,str],
        *,
        end_time: Optional[int] = None,
        timescale='1ns',
        signal_pattern: str = ".",
        add_unnamed_scopes: bool = False
    ) -> int:
        from .simulator import Simulator
        with Simulator(self, str(vcd_file_name), timescale) as context:
            context.dump_signals(signal_pattern=signal_pattern, add_unnamed_scopes=add_unnamed_scopes)
            return context.simulate(end_time)

    def lint(self):
        for module in self.modules:
            assert module in self.module_to_class_map
            module_class_name = self.module_to_class_map[module]
            module_class_base_name = fully_qualified_name(module)
            assert module_class_name in self.module_variants[module_class_base_name]
            assert module in self.module_variants[module_class_base_name][module_class_name]

