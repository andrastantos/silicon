from typing import Union, Set, Tuple, Dict, Any, Optional, List, Iterable, NamedTuple, Sequence, Callable
import typing
from .ordered_set import OrderedSet
from collections import OrderedDict
from .utils import is_input_port, is_output_port, is_wire, is_module, is_port, MEMBER_DELIMITER
from itertools import chain
from .exceptions import SyntaxErrorException

class XNet(object):
    class NameStatus(object):
        def __init__(self, *, is_explicit: bool = True, is_used: bool = False, is_input: bool = False):
            self.is_explicit = is_explicit
            self.is_used = is_used
            self.is_input = is_input

    def __init__(self):
        from .port import Port, Wire
        self.source: Junction = None
        self.sinks: Set[Port] = OrderedSet()
        self.transitions: Set[Port] = OrderedSet()
        self.aliases: Set[Wire] = OrderedSet()
        self.names: Set[str] = OrderedSet()
        self.scoped_names: Dict['Module', Dict[str, 'XNet.NameStatus']] = OrderedDict()
        self.rhs_expressions: Dict['Module', Tuple[str, int]] = OrderedDict()
        self.assigned_names: Dict['Module', str] = OrderedDict()

    def num_junctions(self, *, include_source: bool) -> int:
        return len(self.sinks) + len(self.aliases) + len(self.transitions) + int(self.source is not None and include_source)

    def add_rhs_expression(self, scope: 'Module', expr: str, precedence: int) -> None:
        assert scope is None or is_module(scope)
        assert scope not in self.rhs_expressions
        self.rhs_expressions[scope] = (expr, precedence)
    def get_rhs_expression(self, scope: 'Module', back_end: 'BackEnd') -> Tuple[str, int]:
        assert scope is None or is_module(scope)
        if self.source is None:
            net_type = self.get_net_type()
            if net_type is None:
                raise SyntaxErrorException(f"Can't determine unconnected value for unconnected XNet {xnet}")
            return net_type.get_unconnected_value(back_end), 0
        if scope in self.assigned_names:
            return self.assigned_names[scope], 0
        if scope in self.rhs_expressions:
            return self.rhs_expressions[scope]
        name = self.get_lhs_name(scope, allow_implicit=True)
        if name is None:
            # We end up here with an unconnected input in the instantiation scope, if that input feeds other sub-module inputs within the instance.
            port = self.source
            if port.is_typeless():
                return back_end.get_unconnected_value(), 0
            return port.get_net_type().get_unconnected_value(back_end), 0
        else:
            return name, 0 # This will put the returned value into self.assigned_names
    def get_lhs_name(self, scope: 'Module', *, allow_implicit: bool = True) -> Optional[str]:
        assert scope is None or is_module(scope)
        name = self.get_best_name(scope, allow_implicit=allow_implicit)
        if name is not None:
            self.assign_name(scope, name)
        return name
    def generate_assign(self, sink_name: str, source_expression: str, back_end: 'BackEnd') -> str:
        return self.get_net_type().generate_assign(sink_name, source_expression, self, back_end)
    def add_name(self, scope: 'Module', name: str, *, is_explicit: bool, is_input: bool) -> None:
        assert is_module(scope)
        if scope not in self.scoped_names:
            self.scoped_names[scope] = dict()
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
        # This XNet actually 'lives' in the instantiation scope, yet tere's no way to reference it,
        # so it has no 'best' name
        #assert best_name is not None, "An XNet should have at least one name in every interesting scope"
        return best_name

    def get_net_type(self) -> 'NetType':
        if self.source is not None:
            return self.source.get_net_type()
        for port in self.transitions:
            return port.get_net_type()
        for sink in self.sinks:
            return sink.get_net_type()
        for alias in self.aliases:
            return alias.get_net_type()
        assert False

    @property
    def sim_value(self) -> Any:
        return self.sim_state.value

    def get_num_bits(self) -> int:
        return self.get_net_type().get_num_bits()

class Netlist(object):
    def __init__(self, top_level: 'Module'):
        assert is_module(top_level)
        self.top_level = top_level
        self.modules: Set['Module'] = OrderedSet()
        self.net_types: Dict[str, List['NetType']]= OrderedDict()
        self.ports: Set[object] = OrderedSet()
        self.simulator_context: Optional['Simulator.SimulatorContext'] = None
        self.module_variants: Optional[Dict[type, Dict[str, List['Module']]]] = None
        self.module_to_class_map: Optional[Dict['Module', str]] = None
        self.xnets = OrderedSet()
        self.junction_to_xnet_map = OrderedDict()
        self.module_to_xnet_map = OrderedDict()

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
        if not junction.is_typeless():
            self._register_net_type(junction.get_net_type()) # This is the actual data type carried over the port, such as Logic or a Vector of something...
        if is_port(junction):
            self.ports.add(type(junction)) # This would be 'Input' or 'Output' for most cases

    def register_symbol(self, scope: 'Module', base_name: str, object: Any, delimiter: str = "_") -> str:
        return scope._impl.symbol_table.register_symbol(base_name, object, delimiter)

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
                for member_junction in for_junction.get_member_junctions().values():
                    xnets += create_xnets_for_junction(member_junction)
                return xnets
            else:
                if for_junction.source is not None:
                    # Only create XNets for things that source something. Sinks will get added to existing XNets once the source is identified.
                    return []
                else:
                    x_net = XNet()

                    def trace_x_net(current_junction: Junction):
                        for sink in current_junction.sinks:
                            if is_wire(sink):
                                x_net.aliases.add(sink)
                            else:
                                if len(sink.sinks) == 0:
                                    # No sinks of this junction: this is a terminal node.
                                    x_net.sinks.add(sink)
                                else:
                                    x_net.transitions.add(sink)
                            self.junction_to_xnet_map[sink] = x_net
                            trace_x_net(sink)
                    
                    self.junction_to_xnet_map[for_junction] = x_net
                    trace_x_net(for_junction)

                    if x_net.num_junctions(include_source=True) == 0:
                        # XNet contains only this single junction --> Determine if it's a source-only XNet or a source-less one
                        if is_wire(for_junction):
                            x_net.aliases.add(for_junction)
                        elif is_input_port(for_junction):
                            # This is an XNet with a single input on it. That is: it's an unconnected input.
                            x_net.transitions.add(for_junction)
                            #x_net.source = for_junction
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
                            x_net.sinks.add(for_junction)
                    else:
                        x_net.source = for_junction
                    return [x_net]

        from .port import Junction, Wire, Input, Output
        from .utils import is_port
        for module in self.modules:
            for junction in module.get_junctions().values():
                self.xnets |= create_xnets_for_junction(junction)

        for module in self.modules:
            for port in module.get_ports().values():
                if port not in self.junction_to_xnet_map and not port.is_composite():
                    raise SyntaxErrorException(f"Can't create XNet for port {port}. Most likely reason is that it's connected to itself somehow, creating a trivial combinatorial loop")

    def _fill_xnet_names(self):
        # Fill-in names for xnets
        for xnet in self.xnets:
            from .utils import FQN_DELIMITER
            for scope in xnet.scoped_names.keys():
                if scope not in self.module_to_xnet_map:
                    self.module_to_xnet_map[scope] = OrderedSet()
                self.module_to_xnet_map[scope].add(xnet)
                module_name = scope._impl.get_fully_qualified_name()
                if scope._impl.has_explicit_name:
                    names_in_scope = xnet.get_names(scope)
                    for name in names_in_scope:
                        xnet.names.add(module_name + FQN_DELIMITER + name)

    def _rank_netlist(self) -> Tuple[List[Set['Module']], Dict['Module', int]]:
        """
        Creates a DAG from the netlist (by forcing all non-combinational modules into rank 0)
        Arranges every module by rank in the DAG and returns the DAG

        NOTE: this can only be called after _create_xnets was called
        """
        from .module import Module
        rank_map: Dict[Module, int] = OrderedDict()
        rank_list: List[Set[Module]] = []

        def get_sourced_xnets(module: Module) -> Set[XNet]:
            xnets = OrderedSet()
            for port in module.get_ports().values():
                xnet = self.junction_to_xnet_map[port]
                if xnet.source == port:
                    xnets.add(xnet)
            return xnets

        def get_sinked_xnets(module: Module) -> Set[XNet]:
            xnets = OrderedSet()
            for port in module.get_ports().values():
                for member in port.get_all_member_junctions(add_self=True):
                    xnet = self.junction_to_xnet_map[member]
                    if member in xnet.sinks:
                        xnets.add(xnet)
            return xnets

        def _rank_module(module: Module, iter_level: int = 0) -> int:
            assert iter_level < 100
            if module in rank_map:
                return rank_map[module]
            if not module.is_combinational():
                rank = 0
            else:
                source_xnets = get_sinked_xnets(module)
                if len(source_xnets) == 0:
                    rank = 0
                else:
                    sources = OrderedSet(xnet.source for xnet in source_xnets if xnet.source is not None)
                    source_modules = OrderedSet(source.get_parent_module() for source in sources if source.get_parent_module() is not None)
                    if len(source_modules) == 0:
                        rank = 0
                    else:
                        assert None not in source_modules
                        rank = max(_rank_module(source_module, iter_level + 1) + 1 for source_module in source_modules)
            rank_map[module] = rank
            while len(rank_list) <= rank:
                rank_list.append(OrderedSet())
            rank_list[rank].add(module)
            return rank

        for module in self.modules:
            _rank_module(module)
        for module in self.modules:
            assert module in rank_map

        return rank_list, rank_map

    def get_xnet_for_junction(self, junction: 'Junction') -> 'XNet':
        return self.junction_to_xnet_map[junction]

    def get_xnets_for_junction(self, junction: 'Junction', base_name: str = "<unknown>") -> Dict[str, Tuple['XNet', 'Junction']]:
        if not junction.is_composite():
            return {base_name: (self.get_xnet_for_junction(junction), junction)}
        ret_val = OrderedDict()
        for member_name, member_junction in junction.get_member_junctions().items():
            ret_val.update(self.get_xnets_for_junction(member_junction, f"{base_name}{MEMBER_DELIMITER}{member_name}"))
        return ret_val

    def get_xnets_for_module(self, module: 'Module') -> Set['XNet']:
        assert is_module(module)
        if module not in self.module_to_xnet_map:
            return set()
        return self.module_to_xnet_map[module]

    def _post_elaborate(self) -> None:
        """
        Called from the elaborate of the top level module.

        This method deals with all the cleanup after elaboration.

        For now, it consists of:
        - Generate module and net names
        - Creation of XNets
        - Ranking modules into logic cones
        - Sorting all the modules into instance classes. That is, create a set of module instances whom share the same implementation.
          This is a bit more complex then simply looking at their type or __class__: generic modules or modules with dynamic port creation
          support may not share the body even if they are of the same class.
        """
        def populate_names(module: 'Module'):
            from .module import Module
            module._impl.create_symbol_table()
            module._impl.populate_submodule_names(self)
            module._impl.populate_xnet_names(self)
            for sub_module in module._impl.get_sub_modules():
                populate_names(sub_module)

        def populate_module_variants(module: 'Module'):
            # First recurse into all sub-modules, then deal with this one...
            for sub_module in module._impl.get_sub_modules():
                populate_module_variants(sub_module)

            assert module not in self.module_to_class_map

            module_class = module.__class__
            found = False
            if module_class not in self.module_variants:
                self.module_variants[module_class] = OrderedDict()
            else:
                for variant_name, variant_instances in self.module_variants[module_class].items():
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
                #We need to come up with a module class name
                variant_cnt = len(self.module_variants[module_class])
                if variant_cnt == 0:
                    module_class_name = module_class.__name__
                else:
                    module_class_name = module_class.__name__ + "_" + str(variant_cnt+1)
                self.module_variants[module_class][module_class_name] = [module]
                self.module_to_class_map[module] = module_class_name

        def register_modules(module: 'Module'):
            self.register_module(module)
            for sub_module in module._impl.get_sub_modules():
                register_modules(sub_module)

        register_modules(self.top_level)
        self._create_xnets()
        populate_names(self.top_level)
        self._fill_xnet_names()
        self.rank_list, self.rank_map = self._rank_netlist()
        self.module_variants = OrderedDict()
        self.module_to_class_map = OrderedDict()
        populate_module_variants(self.top_level)
        # Make sure we've to everyone
        for module in self.modules:
            assert module in self.module_to_class_map
    
    def get_module_class_name(self, module_instance: 'Module') -> Optional[str]:
        assert is_module(module_instance)
        if module_instance not in self.module_to_class_map:
            return None
        return self.module_to_class_map[module_instance]

    def register_module(self, module: 'Module'):
        assert is_module(module)
        self.modules.add(module)
        for junction in module.get_junctions().values():
            self._register_junction(junction)

    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> None:
        from .utils import str_block
        
        streams = back_end.generate_order(self)

        self.top_level._impl._generate_needed = True
        for stream, (modules, types) in streams.items():
            with stream as strm:
                type_impls = ""
                for net_type in types:
                    type_impl = net_type.generate(self, back_end)
                    if type_impl is not None:
                        type_impls = str_block(type_impl, "", "\n\n")
                strm.write(str_block(type_impls, "/"*80+"\n// Type definitions\n"+"/"*80+"\n", "\n\n\n"))

                for module in reversed(modules):
                    module_impl = module._impl._generate(self, back_end)
                    if module_impl is not None:
                        strm.write(str_block(module_impl, "", "\n\n\n"))
                    # Mark all instances of the same variant as no body needed
                    module_class = module.__class__
                    module_class_name = self.module_to_class_map[module]
                    for module_inst in self.module_variants[module_class][module_class_name]:
                        module_inst._impl._generate_needed = False
                        module_inst._impl._body_generated = True

    def simulate(self, vcd_file_name: str, end_time: Optional[int] = None, timescale='1ns') -> int:
        from .simulator import Simulator
        with Simulator(self, vcd_file_name, timescale) as context:
            context.dump_signals()
            import cProfile as profile
            import pstats as pstats
            import io as io
            pr = profile.Profile()
            pr.enable()
            ret_val = context.simulate(end_time)
            pr.disable()
            s = io.StringIO()
            sortby = 'cumulative'
            ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
            #ps.print_stats()
            ps.dump_stats("profile.out")
            #print(s.getvalue())
            return ret_val

    def lint(self):
        for module in self.modules:
            assert module in self.module_to_class_map
            module_class_name = self.module_to_class_map[module]
            module_class = module.__class__
            assert module_class_name in self.module_variants[module_class]
            assert module in self.module_variants[module_class][module_class_name]
    
