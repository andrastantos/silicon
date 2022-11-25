from abc import abstractmethod
from typing import Tuple, Dict, Optional, Set, Any, Type, Sequence
import inspect
from .net_type import NetType, KeyKind, NetTypeMeta
from .ordered_set import OrderedSet
from .exceptions import SyntaxErrorException, SimulationException
from .utils import convert_to_junction, is_iterable, is_junction_base, is_input_port, is_output_port, get_caller_local_junctions, is_module, MEMBER_DELIMITER, Context, is_net_type, first
from .port import KeyKind
from collections import OrderedDict
from enum import Enum


class IgnoreMeAfterIlShift(object):
    pass

class JunctionBase(object):
    """
    Pretty much same as Junction, but allows for wrappers, such as ScopedPort.

    At this point, the only two things deriving from JunctionBase are
    Junction (d'uh) and ScopedPort.
    """
    def __new__(cls, *args, **kwargs):
        # Clean up all arguments before passing down the __new__-chain.
        # This is important, because - for typed ports - we'll eventually
        # end up in NetType.__new__ which is tricky. It uses the number of
        # arguments passed in to determine if we wanted a type-cast or a new
        # type instance. 
        return super().__new__(cls)

    def __init__(self, parent_module: Optional['Module'] = None):
        # !!!!! SUPER IMPORTANT !!!!!
        # In most cases, Ports of a Module are set on the cls level, not inside __init__() (or construct()).
        # There is a generic 'deepcopy' call in _init_phase2 that creates the instance-level copies for all the ports.
        # This means that __init__ for those ports is not getting called, the instance-level port is not a brand new
        # object, it's a copy of an already live one. This means, that none of this code gets executed for instance-level
        # ports. Things that *do* need to get executed in all contexts, should go into '_init_phase2'. That in turn
        # will get called from '_init_phase2' of 'Module'.
        assert parent_module is None or is_module(parent_module)

        super().__init__()
        self._parent_module = parent_module
        self._allow_auto_bind = True
        self._no_rtl = False # If set to true, we'll try to not generate RTL code for this junction, by not registering it in Tracer or in _body
        self._scoped_ports = []
        if parent_module is not None:
            self._init_phase2(parent_module)

    def _init_phase2(self, parent_module: 'Module'):
        assert parent_module is not None
        self._parent_module = parent_module
        Context.register(self._context_change)
        parent_module._impl.netlist.symbol_table[parent_module].add_auto_symbol(self)

    def __getitem__(self, key: Any) -> Any:
        if Context.current() == Context.simulation:
            return self.get_net_type().get_slice(key, self)
        else:
            from .member_access import UniSlicer
            return UniSlicer(self, key, KeyKind.Index, self.get_parent_module())

    def __setitem__(self, key: Any, value: Any) -> None:
        if value is IgnoreMeAfterIlShift:
            return
        raise SyntaxErrorException("Assignment to slices is not supported. Use the '<<=' operator instead")

    def __delitem__(self, key: Any) -> None:
        # I'm not sure what this even means in this context
        raise TypeError()

    def __enter__(self) -> 'Junction':
        self._allow_auto_bind = True
        scoped_port = ScopedPort(convert_to_junction(self))
        self._scoped_ports.append((scoped_port, get_caller_local_junctions(2)))
        return scoped_port


    def __exit__(self, exception_type, exception_value, traceback):
        self._allow_auto_bind = False
        # TODO: This can be perf optimized: we iterate twice, once in get_caller_local_junctions and once here...
        junctions_after_scope = get_caller_local_junctions(2)
        found = False
        scoped_port, junctions_before_scope = self._scoped_ports[-1]
        for name, junction in junctions_after_scope.items():
            try:
                junction_scoped_port = junction.get_underlying_scoped_port()
            except AttributeError:
                continue
            if junction_scoped_port is scoped_port:
                old_junction = junctions_before_scope.get(name, None)
                if old_junction is not None and found:
                    raise SyntaxErrorException(f"This is not supported: scoped port {self} got assigned to multiple already existing local net references. Can't restore originals.")
                scoped_port._update_real_port(old_junction)
                found = True
        junction = None
        del junctions_after_scope
        del self._scoped_ports[-1]

    def get_parent_module(self) -> Optional['Module']:
        return self._parent_module

    @staticmethod
    def _safe_call_by_name(obj, name, *kargs, **kwargs):
        if obj is None:
            return None
        return getattr(type(obj), name)(obj, *kargs, **kwargs)

    def _binary_op(self, other: Any, gate: 'Module', name: str) -> Any:
        context = Context.current()
        if context == Context.simulation:
            my_val = self.sim_value
            return JunctionBase._safe_call_by_name(my_val, name, other)
        elif context == Context.elaboration:
            return gate(self, other)
        else:
            sup = super()
            return getattr(sup, name)(other)

    def _rbinary_op(self, other: Any, gate: 'Module', name: str) -> Any:
        context = Context.current()
        if context == Context.simulation:
            my_val = self.sim_value
            return JunctionBase._safe_call_by_name(my_val, name, other)
        elif context == Context.elaboration:
            return gate(other, self)
        else:
            sup = super()
            return getattr(sup, name)(other)

    def _unary_op(self, gate: 'Module', name: str) -> Any:
        context = Context.current()
        if context == Context.simulation:
            my_val = self.sim_value
            return JunctionBase._safe_call_by_name(my_val, name)
        elif context == Context.elaboration:
            return gate(self)
        else:
            sup = super()
            return getattr(sup, name)()

    def _ninput_op(self, other: Any, gate: 'Module', name: str) -> Any:
        context = Context.current()
        if context == Context.simulation:
            my_val = self.sim_value
            if my_val is None: return None
            return JunctionBase._safe_call_by_name(my_val, name, other)
        elif context == Context.elaboration:
            return gate(self, other)
        else:
            sup = super()
            return getattr(sup, name)(other)

    def _rninput_op(self, other, gate: 'Module', name: str) -> Any:
        context = Context.current()
        if context == Context.simulation:
            my_val = self.sim_value
            return JunctionBase._safe_call_by_name(my_val, name, other)
        elif context == Context.elaboration:
            return gate(other, self)
        else:
            sup = super()
            return getattr(sup, name)(other)


    def __add__(self, other: Any) -> Any:
        from .gates import sum_gate as gate
        return self._ninput_op(other, gate, "__add__")

    def __sub__(self, other: Any) -> Any:
        from .gates import sub_gate as gate
        return self._binary_op(other, gate, "__sub__")

    def __mul__(self, other: Any) -> Any:
        from .gates import prod_gate as gate
        return self._ninput_op(other, gate, "__mul__")

    #def __floordiv__(self, other: Any) -> Any:
    #def __mod__(self, other: Any) -> Any:
    #def __divmod__(self, other: Any) -> Any:
    #def __pow__(self, other: Any, modulo = None) -> Any:
    #def __truediv__(self, other: Any) -> Any:

    def __lshift__(self, other: Any) -> Any:
        from .gates import lshift_gate as gate
        return self._binary_op(other, gate, "__lshift__")

    def __rshift__(self, other: Any) -> Any:
        from .gates import rshift_gate as gate
        return self._binary_op(other, gate, "__rshift__")

    def __and__(self, other: Any) -> Any:
        from .gates import and_gate as gate
        return self._ninput_op(other, gate, "__and__")

    def __xor__(self, other: Any) -> Any:
        from .gates import xor_gate as gate
        return self._ninput_op(other, gate, "__xor__")

    def __or__(self, other: Any) -> Any:
        from .gates import or_gate as gate
        return self._ninput_op(other, gate, "__or__")



    def __radd__(self, other: Any) -> Any:
        from .gates import sum_gate as gate
        return self._rninput_op(other, gate, "__radd__")

    def __rsub__(self, other: Any) -> Any:
        from .gates import sub_gate as gate
        return self._rbinary_op(other, gate, "__rsub__")

    def __rmul__(self, other: Any) -> Any:
        from .gates import prod_gate as gate
        return self._rninput_op(other, gate, "__rmul__")

    #def __rtruediv__(self, other: Any) -> Any:
    #def __rfloordiv__(self, other: Any) -> Any:
    #def __rmod__(self, other: Any) -> Any:
    #def __rdivmod__(self, other: Any) -> Any:
    #def __rpow__(self, other: Any) -> Any:

    def __rlshift__(self, other: Any) -> Any:
        from .gates import lshift_gate as gate
        return self._rbinary_op(other, gate, "__rlshift__")

    def __rrshift__(self, other: Any) -> Any:
        from .gates import rshift_gate as gate
        return self._rbinary_op(other, gate, "__rrshift__")

    def __rand__(self, other: Any) -> Any:
        from .gates import and_gate as gate
        return self._rninput_op(other, gate, "__rand__")

    def __rxor__(self, other: Any) -> Any:
        from .gates import xor_gate as gate
        return self._rninput_op(other, gate, "__rxor__")

    def __ror__(self, other: Any) -> Any:
        from .gates import or_gate as gate
        return self._rninput_op(other, gate, "__ror__")


    #def __iadd__(self, other: Any) -> Any:
    #def __isub__(self, other: Any) -> Any:
    #def __imul__(self, other: Any) -> Any:
    #def __idiv__(self, other: Any) -> Any:
    #def __itruediv__(self, other: Any) -> Any:
    #def __ifloordiv__(self, other: Any) -> Any:
    #def __imod__(self, other: Any) -> Any:
    #def __ipow__(self, other: Any, modulo = None) -> Any:
    #def __ilshift__(self, other: Any) -> Any:
    #def __irshift__(self, other: Any) -> Any:
    #def __iand__(self, other: Any) -> Any:
    #def __ixor__(self, other: Any) -> Any:
    #def __ior__(self, other: Any) -> Any:

    def __neg__(self) -> Any:
        from .gates import neg_gate as gate
        return self._unary_op(gate, "__neg__")

    def __pos__(self) -> Any:
        return self

    def __abs__(self) -> Any:
        from .gates import abs_gate as gate
        return self._unary_op(gate, "__abs__")

    def __invert__(self) -> Any:
        from .gates import not_gate as gate
        context = Context.current()
        if context == Context.simulation:
            my_val = self.sim_value
            try:
                return my_val.invert(self.get_num_bits())
            except AttributeError:
                return self._unary_op(gate, "__invert__")
        else:
            return self._unary_op(gate, "__invert__")


    #def __complex__(self) -> Any:
    #def __int__(self) -> Any:
    #def __long__(self) -> Any:
    #def __float__(self) -> Any:
    #def __oct__(self) -> Any:
    #def __hex__(self) -> Any:
    #def __index__(self) -> Any:


    def __bool__(self) -> bool:
        from .gates import bool_gate as gate
        return self._unary_op(gate, "__bool__")

    def __lt__(self, other: Any) -> bool:
        from .gates import lt_gate as gate
        return self._binary_op(other, gate, "__lt__")

    def __le__(self, other: Any) -> bool:
        from .gates import le_gate as gate
        return self._binary_op(other, gate, "__le__")

    def __eq__(self, other: Any) -> bool:
        from .gates import eq_gate as gate
        return self._binary_op(other, gate, "__eq__")

    def __ne__(self, other: Any) -> bool:
        from .gates import ne_gate as gate
        return self._binary_op(other, gate, "__ne__")

    def __gt__(self, other: Any) -> bool:
        from .gates import gt_gate as gate
        return self._binary_op(other, gate, "__gt__")

    def __ge__(self, other: Any) -> bool:
        from .gates import ge_gate as gate
        return self._binary_op(other, gate, "__ge__")

    def ilshift__elab(self, other: Any) -> 'Junction':
        assert False, "We shouldn't ever be here!!!"

    def ilshift__none(self, other: Any) -> 'Junction':
        assert False, "We shouldn't ever be here!!!"
        return super().__ilshift__(other)

    def ilshift__impl(self, other: Any) -> 'Junction':
        assert False, "We shouldn't ever be here!!!"
        return self.__ilshift__none(other)

    def __ilshift__(self, other: Any) -> 'Junction':
        return self.__ilshift__impl(other)

    @abstractmethod
    def ilshift__sim(self, other: Any) -> 'Junction':
        raise NotImplementedError()

    def _context_change(self, context: Context) -> None:
        if context is None:
            self.__ilshift__impl = self.ilshift__none
        elif context == Context.simulation:
            self.__ilshift__impl = self.ilshift__sim
        elif context == Context.elaboration:
            self.__ilshift__impl = self.ilshift__elab
        else:
            assert False

    @abstractmethod
    def set_source(self, source: Any, scope: 'Module') -> None:
        raise NotImplementedError()

    def allow_auto_bind(self) -> bool:
        """
        Determines if auto-binding to this junction is allowed.
        Defaults to True, but for scoped ports, get set to False
        upon __exit__
        """
        return self._allow_auto_bind

    def allow_bind(self) -> bool:
        """
        Determines if binding to this junction is allowed.
        Defaults to True, but for scoped junctions, get set to
        False to disallow shananingans, like this:
            with my_port as x:
                x <<= 3
        """
        return True

    def __hash__(self):
        return id(self)





class EdgeType(Enum):
    NoEdge = 0
    Positive = 1
    Negative = 2
    Undefined = 3

class Junction(JunctionBase):
    class NetEdge(object):
        def __init__(self, far_end: 'Junction', scope: 'Module'):
            self.far_end = far_end
            self.scope = scope

    def __init__(self, net_type: Optional[NetTypeMeta] = None, parent_module: 'Module' = None, *, keyword_only: bool = False):
        # !!!!! SUPER IMPORTANT !!!!!
        # In most cases, Ports of a Module are set on the cls level, not inside __init__() (or construct()).
        # There is a generic 'deepcopy' call in _init_phase2 that creates the instance-level copies for all the ports.
        # This means that __init__ for those ports is not getting called, the instance-level port is not a brand new
        # object, it's a copy of an already live one. This means, that none of this code gets executed for instance-level
        # ports. Things that *do* need to get executed in all contexts, should go into '_init_phase2'. That in turn
        # will get called from '_init_phase2' of 'Module'.
        super().__init__(parent_module)
        from .module import Module
        self._partial_sources: Sequence[Tuple[Optional[Sequence[Tuple[Any, KeyKind]]], 'Junction.NetEdge']] = [] # contains slice/member assignments
        self._sinks: Dict['Junction', 'Module'] = {}
        self._in_attr_access = False
        self.keyword_only = keyword_only
        self._member_junctions = OrderedDict() # Contains members for struct/interfaces/vectors
        self._parent_junction = None # Reverences back to the container for struct/interface/vector members
        self._net_type = None
        self._xnet = None # This is set by Netlist to cache the result of Netlist.get_xnet_for_junction(self)
        if net_type is not None:
            if not is_net_type(net_type):
                raise SyntaxErrorException(f"Net type for a port must be a subclass of NetType.")
            self.set_net_type(net_type)


    def __str__(self) -> str:
        ret_val = self.get_diagnostic_name()
        if not self.is_specialized():
            return ret_val
        ret_val += ": " + str(self.get_net_type())
        if not hasattr(self, "_xnet") or self._xnet is None:
            return ret_val
        ret_val += f" = {self._xnet.sim_state.value}"
        return ret_val

    def ilshift__elab(self, other: Any) -> 'Junction':
        if self.has_source():
            raise SyntaxErrorException(f"{self} is already bound to {', '.join((str(src.far_end) for _, src in self._partial_sources))}.")
        from .netlist import Netlist
        self.set_source(other, Netlist.get_current_scope())
        return self

    def get_underlying_junction(self) -> Optional['Junction']:
        """
        Returns the underlying port object. For most ports, it's just 'self', but for scoped ports and JunctionRefs, it's the underlying port
        """
        return self

    def get_all_sinks(self) -> Set['Junction']:
        """
        Returns the transitive closure of the sink-chain,
        that is all junctions that sink from this port.

        Of course this might be incomplete if the netlist
        is still under construction.
        """
        ret_val = set()
        for sink in self.sinks:
            ret_val.add(sink)
            ret_val |= sink.get_all_sinks()
        return ret_val


    def set_parent_module(self, parent_module: 'Module') -> None:
        assert parent_module is None or is_module(parent_module)
        assert self._parent_module is None or self._parent_module is parent_module
        assert self._parent_junction is None or self._parent_junction._parent_module is parent_module
        if self._parent_module is None:
            self._init_phase2(parent_module)
        # Recurse into members
        for member_junction, _ in self.get_member_junctions().values():
            member_junction.set_parent_module(parent_module)

    def resolve_multiple_sources(self, scope) -> None:
        if self.is_composite():
            for member, _ in self.get_member_junctions().values():
                member.resolve_multiple_sources(scope)
        else:
            if len(self._partial_sources) > 0:
                from silicon.member_access import PhiSlice

                key_chains = tuple(partial_source[0] for partial_source in self._partial_sources if partial_source[0] is not None)
                sources = tuple(partial_source[1].far_end for partial_source in self._partial_sources if partial_source[0] is not None)
                #scopes = tuple(partial_source[1].scope for partial_source in self._partial_sources if partial_source[0] is not None)
                if len(key_chains) > 0:
                    # Make sure we don't have both full and partial assignments to the same junction
                    if len(key_chains) != len(self._partial_sources):
                        raise SyntaxErrorException(f"You can't have both partial and full assignment to junction '{self}'")
                    self.phi_slice = PhiSlice(key_chains)
                    self._partial_sources = [] # Remove all sources: we're handling them in a PhySlice instance from now on
                    self.set_source(self.phi_slice(*sources), scope)

    def get_junction_type(self) -> type:
        if type(self) is Junction:
            return Junction
        for cls in inspect.getmro(type(self))[1:]:
            if issubclass(cls, Junction):
                return cls

    def set_net_type(self, net_type: Optional[NetType]) -> None:
        # Only allow the net_type to be set if it's not yet set.
        if self._net_type is net_type:
            return
        assert not self.is_specialized()
        if net_type is not None:
            self._net_type = net_type
            # We replace the empty intermediary class with the behaviors from net_type:
            behavior_obj = net_type.get_behaviors()
            if behavior_obj is not None:
                extra_bases = (type(behavior_obj), )
                extra_dict = behavior_obj.__dict__
            else:
                extra_bases = None
                extra_dict = None
            self.__class__ = create_junction_type(self.get_junction_type(), net_type, extra_bases, extra_dict)
            net_type.setup_junction(self)
            self.connect_composite_members()
            # If we got a type, our sinks might be able to connect their members too...
            for sink in self._sinks.keys():
                sink.connect_composite_members()

    def has_driver(self, allow_non_auto_inputs: bool = False) -> bool:
        """
        Returns True if the port can possibly have a driver (source-chain ends in a wire or an Output)
        """
        # For compound types, we can't easily answer this question. It's the individual members that may or may not have drivers.
        if self.is_composite():
            return False
        junction = self
        while junction.has_source():
            for _, source_edge in self._partial_sources:
                source = source_edge.far_end
                if is_input_port(source) and (allow_non_auto_inputs or source._auto):
                    src_has_driver = source.has_driver(allow_non_auto_inputs)
                    if src_has_driver:
                        return True
                else:
                    return True
        # There's no driver. However, we should assume that top level ports have drivers, no matter what
        if junction.get_parent_module()._impl.is_top_level():
            return True
        return False

    def get_net_type(self) -> Optional[NetType]:
        return self._net_type
    def is_specialized(self) -> bool:
        if "_net_type" not in self.__dict__:
            return False
        return self._net_type is not None

    def connect_composite_members(self):
        # If called on an untyped port or on an edge with not yet resolved type incompatibilities, bail out
        if not self.is_specialized():
            return
        if not self.has_source():
            return
        source = self.get_source()
        assert source is not None
        scope = self.source_scope
        if self.is_composite():
            if not source.is_specialized():
                return
                assert False
                # It's possible that the source doesn't quite yet have a type (for example the result of a Select on a Struct).
                # In that case, we back-propagate the sinks' type to the source.
                sinks = source.get_all_sinks()
                for sink in sinks:
                    if sink.is_specialized() and self.get_net_type() != sink.get_net_type():
                        raise SyntaxErrorException(f"A sink of junction {source} ({sink}) is of the wrong type. All sinks should have type {source.get_net_type()}.")
                source.set_net_type(self.get_net_type())
            if self.get_net_type() is not source.get_net_type():
                return

            for member_name, (member_junction, reversed) in self.get_member_junctions().items():
                if reversed:
                    source.get_member_junctions()[member_name][0].set_source(member_junction, scope=scope)
                else:
                    member_junction.set_source(source.get_member_junctions()[member_name][0], scope=scope)

            """
            # We have to take care of registering the members as hard or soft-symbols in all the scopes of ourselves
            # There can be two scopes (we don't deal with XNets yet): the parent module and it's parent
            from .sym_table import SymbolTable, ScopeTable
            from typing import List
            symbol_table: SymbolTable = self.get_parent_module()._impl.netlist.symbol_table
            parent_parent = self.get_parent_module()._impl.parent
            scopes: List[ScopeTable] = []
            scopes.append(symbol_table[self._parent_module])
            if parent_parent is not None:
                scopes.append(symbol_table[parent_parent])
            for member_name, (member_junction, reversed) in self.get_member_junctions().items():
                for scope in scopes:
                    for name in scope.get_hard_names(self):
                        m_name = f"{name}{MEMBER_DELIMITER}{member_name}"
                        print(f"*********** REGISTERING HARD SYMBOL {m_name} for {name}")
                        scope.add_hard_symbol(member_junction, m_name)
                    for name in scope.get_soft_names(self):
                        m_name = f"{name}{MEMBER_DELIMITER}{member_name}"
                        print(f"*********** REGISTERING HARD SYMBOL {m_name} for {name}")
                        scope.add_soft_symbol(member_junction, m_name)

            """
    def _del_source(self) -> None:
        """
        Removes all potentially existing binding between this port and its (partial) source(s)
        """
        seen_sources = set() # This is not strictly needed, but I put it in for verification
        for key, source_edge in self._partial_sources:
            source = source_edge.far_end
            if self.is_composite() and source is not None:
                for member_name, (member_junction, reversed) in self.get_member_junctions().items():
                    if reversed:
                        # It's possible that the source doesn't have a type, in which case this will fail. That's fine
                        try:
                            source.get_member_junctions()[member_name][0]._del_source()
                        except KeyError:
                            pass
                    else:
                        member_junction._del_source()
            # For some reason partial sources don't register as sinks on the other end????
            if source not in seen_sources:
                del source._sinks[self]
            seen_sources.add(source)
        self._partial_sources.clear()

    @property
    def sinks(self):
        return tuple(self._sinks.keys())

    def _get_source_edge(self):
        found_edge = None
        for key, source_edge in self._partial_sources:
            if key is not None:
                continue
            assert found_edge is None
            found_edge = source_edge
        return found_edge

    def has_source(self, allow_partials: bool = True) -> bool:
        """
        Returns True if Port has a source, False otherwise.

        set allow_partials to False, to only count full sources.
        """
        if allow_partials:
            return len(self._partial_sources) > 0
        else:
            for key, source_edge in self._partial_sources:
                if key is None:
                    return True
            return False

    def get_source(self) -> 'JunctionBase':
        # TODO: in fact this should die: we don't have a concept of a unique source anymore.
        source_edge = self._get_source_edge()
        if source_edge is None: return None
        return source_edge.far_end
    @property
    def source_scope(self):
        # TODO: in fact this should die: we don't have a concept of a unique source anymore.
        source_edge = self._get_source_edge()
        if source_edge is None: return None
        return source_edge.scope

    def set_source(self, source: Any, scope: 'Module') -> None:
        passed_in_source = source
        if source is not None:
            source = convert_to_junction(source, type_hint=None)
            if source is None:
                # We couldn't create a port out of the value:
                raise SyntaxErrorException(f"couldn't convert '{passed_in_source}' to Junction.")
            assert isinstance(source, Junction)

        self._del_source()
        self._partial_sources.append((None, Junction.NetEdge(source, scope)))
        assert self not in source._sinks.keys()
        source._sinks[self] = scope
        self.connect_composite_members()

        # TODO: deal with this through inheritance instead of type-check!
        if is_output_port(source):
            parent_module = source.get_parent_module()
            if parent_module is not None:
                parent_parent_module = parent_module._impl.parent
                if parent_parent_module is not None:
                    # It is OK to call this multiple times for the same sub_module. After the first one, it's a no-op.
                    parent_parent_module._impl.order_sub_module(parent_module)

    def replace_source(self, old_source: Any, new_source: Any, scope: 'Module') -> None:
        """
        Replace all references of old_source to new_source within our sources (partial or otherwise)
        """
        # TODO: is there a faster way than iterating all sources? Seems it scaled poorly, but maybe it doesn't matter.
        for key, source_edge in self._partial_sources:
            if source_edge.far_end is old_source:
                source_edge.far_end = new_source
                source_edge.scope = scope
                del old_source._sinks[self]
                new_source._sinks[self] = scope
        
    def set_partial_source(self, key_chain: Sequence[Tuple[Any, KeyKind]], source: Any, scope: 'Module') -> None:
        passed_in_source = source
        if source is not None:
            source = convert_to_junction(source, type_hint=None)
            if source is None:
                # We couldn't create a port out of the value:
                raise SyntaxErrorException(f"couldn't convert '{passed_in_source}' to Junction.")
            assert isinstance(source, Junction)

        self._partial_sources.append(
            (key_chain, Junction.NetEdge(source, scope))
        )
        # It's possible that a source supplies multiple parts of a sink. For instance: a[3] <<= b ... a[0] <<= b
        if self not in source._sinks.keys():
            source._sinks[self] = scope

        # TODO: deal with this through inheritance instead of type-check!
        if is_output_port(source):
            parent_module = source.get_parent_module()
            if parent_module is not None:
                parent_parent_module = parent_module._impl.parent
                if parent_parent_module is not None:
                    # It is OK to call this multiple times for the same sub_module. After the first one, it's a no-op.
                    parent_parent_module._impl.order_sub_module(parent_module)

    def generate_interface(self, back_end: 'BackEnd', port_name: str) -> Sequence[str]:
        assert back_end.language == "SystemVerilog"
        if not self.is_composite():
            return [f"{self.get_net_type().generate_net_type_ref(self, back_end)} {port_name}"]
        else:
            ret_val = []
            for member_name, (member_junction, _) in self._member_junctions.items():
                ret_val += member_junction.generate_interface(back_end, f"{port_name}{MEMBER_DELIMITER}{member_name}")
            return ret_val

    def __iter__(self) -> Any:
        if not self.is_specialized():
            raise SyntaxErrorException(f"Can only iterate through the elements of a specialized port.")
        return self.get_net_type().get_iterator(self)

    def __len__(self) -> int:
        if not self.is_specialized():
            raise SyntaxErrorException(f"Can only determine the length of a specialized port.")
        net_type = self.get_net_type()
        if not hasattr(net_type, "get_length"):
            raise SyntaxErrorException(f"Net {self} of type {net_type} doesn't support 'len'")
        return net_type.get_length()

    @property
    def junction_kind(self) -> str:
        raise NotImplementedError

    @classmethod
    def generate_junction_ref(cls, back_end: 'BackEnd') -> str:
        raise NotImplementedError

    @classmethod
    def is_instantiable(cls) -> bool:
        raise NotImplementedError

    @property
    def sim_value(self) -> Any:
        #if not hasattr(self, "_xnet") or self._xnet is None:
        #    return None
        #assert not self.is_composite(), "Simulator should never ask for the value of compound types"
        #return self._xnet.sim_state.value
        class CompositeSimValue(object):
            pass

        if self.is_composite():
            sim_value = CompositeSimValue()
            for member_name, (member_junction, reversed) in self.get_member_junctions().items():
                setattr(sim_value, member_name, member_junction.sim_value)
            return sim_value
        return self._xnet.sim_value

    @property
    def previous_sim_value(self) -> Any:
        #if not hasattr(self, "_xnet") or self._xnet is None:
        #    return None
        assert not self.is_composite(), "Simulator should never ask for the value of compound types"
        return self._xnet.sim_state.previous_value
    def get_sim_edge(self) -> EdgeType:
        #if not hasattr(self, "_xnet") or self._xnet is None:
        #    return None
        assert not self.is_composite(), "Simulator should never ask for the value of compound types"
        if not self._xnet.sim_state.is_edge():
            return EdgeType.NoEdge
        if self.previous_sim_value == 0 and self.sim_value == 1:
            return EdgeType.Positive
        if self.previous_sim_value == 1 and self.sim_value == 0:
            return EdgeType.Negative
        return EdgeType.Undefined

    @property
    def vcd_type(self) -> str:
        """
        Returns the associated VCD type (one of VAR_TYPES inside vcd.writer.py)
        Must be overwritten for all sub-classes
        """
        assert not self.is_composite(), "Simulator should never ask for the vcd type of compound types"
        return self.get_net_type().vcd_type
    def get_num_bits(self) -> int:
        return self.get_net_type().get_num_bits()
    def get_diagnostic_name(self, add_location: bool = True) -> str:
        """
        Returns a name that's best suited for diagnostic messages
        """
        if self.get_parent_module() is None:
            return "<floating>"
        from .utils import FQN_DELIMITER
        parent_module = self.get_parent_module()
        module_name = parent_module._impl.get_diagnostic_name(False)
        scope_table = parent_module._impl.netlist.symbol_table[parent_module]
        names = scope_table.get_names(self)
        if len(names) == 0:
            name = "<unknown>"
        else:
            name = first(names)
        name = module_name + FQN_DELIMITER + name
        if add_location:
            name += self.get_parent_module()._impl.get_diagnostic_location(" at ")
        return name




    def ilshift__sim(self, other: Any) -> 'Junction':
        if self.is_composite():
            if other is None:
                for self_member in self.get_all_member_junctions(add_self=False):
                    self_member._set_sim_val(None)
            elif is_junction_base(other):
                # If something is connected to an otherwise unconnected port, we should support that.
                if not other.has_source():
                    for self_member in self.get_all_member_junctions(add_self=False):
                        self_member._set_sim_val(None)
                else:
                    if self.get_net_type() is not other.get_net_type():
                        raise SimulationException(f"Assignment to compound types during simulation is only supported between identical net types", self)
                    for self_member, other_member in zip(self.get_all_member_junctions(add_self=False), other.get_all_member_junctions(add_self=False)):
                        self_member._set_sim_val(other_member)
            elif is_iterable(other):
                members = self.get_member_junctions()
                if len(other) != len(members):
                    raise SimulationException(f"Assignment to composite type should contain {len(members)} elements. It has {len(other)} elements", self)
                # Try it as a dict first, and if it fails, use it as a list
                try:
                    for name, value in other.item():
                        if name not in members:
                            raise SimulationException(f"Attempt to assign to nonexistent member {name}", self)
                        members[name] <<= value
                except AttributeError:
                    for (member, _), value in zip(members.values(), other):
                        member <<= value
            else:
                raise SimulationException(f"Unsupported assignment to composite type simulation", self)
        else:
            self._set_sim_val(other)
        return self

    def _set_sim_val(self, value: Any, when: Optional[int] = None) -> None:
        assert not self.is_composite(), "Simulator should never set the value of compound types"
        # using hasattr instead of is_junction_base to speed up simulation. It also catches PortSlices not just Ports
        if hasattr(value, "sim_value"):
            new_sim_value = value.sim_value
        else:
            from .utils import adapt
            new_sim_value = adapt(value, self.get_net_type(), implicit=False, force=False)

        if self._xnet.source is not self and self._xnet.source is not None:
            is_transition = self in self._xnet.transitions
            is_sink = self in self._xnet.sinks
            assert is_transition or is_sink
            raise SimulationException(f"Can't assigned to net that has a driver during simulation. This net is a {'transition, which means it both has a driver and sink(s)' if is_transition else 'sink, which means it does not drive anything'}", self)
        if self._xnet.source is self:
            self._xnet.sim_state.sim_context.schedule_value_change(self._xnet, new_sim_value, when)


    ############################################
    # Compund type support
    ############################################
    @classmethod
    def get_member_junction_kind(cls, is_reversed: bool) -> Type:
        raise NotImplementedError

    class MemberJunctionProperty(property):
        def __init__(self, name):
            def fget(obj):
                return obj._member_junctions[name][0]
            def fset(obj, value):
                if obj._member_junctions[name][0] is not value:
                    raise SyntaxErrorException("Can't assign to member junction: use the '<<=' operator")
                #obj._member_junctions[name][0] <<= value
            super().__init__(fget=fget, fset=fset)

    def create_member_junction(self, name: str, net_type: 'NetType', reversed: bool) -> None:
        assert self.is_specialized(), "Can only add members to a specialized port. In fact, create_member_junction should only be called from the junctions type."
        junction_type = self.get_member_junction_kind(reversed)
        member = junction_type(net_type, self.get_parent_module())

        # It's possible that we don't have a parent module if this is a class-level composite port:
        #
        #    class MyModule(Module):
        #        MyInput = Input(MyComposite)
        #    ...
        if self._parent_module is not None:
            scope_table = self._parent_module._impl.netlist.symbol_table[self._parent_module]
            for parent_name in scope_table.get_hard_names(self):
                scope_table.add_hard_symbol(member, f"{parent_name}{MEMBER_DELIMITER}{name}")
            for parent_name in scope_table.get_soft_names(self):
                scope_table.add_soft_symbol(member, f"{parent_name}{MEMBER_DELIMITER}{name}")
        member._parent_junction = self
        self._member_junctions[name] = [member, reversed]
        setattr(self.__class__, name, Junction.MemberJunctionProperty(name))

    def is_composite(self) -> bool:
        return len(self._member_junctions) > 0

    def is_member(self) -> bool:
        return self._parent_junction is not None

    def get_member_junctions(self) -> Dict[str, Tuple['Junction', bool]]:
        return self._member_junctions

    def get_all_member_junctions(self, add_self: bool) -> Sequence['Junction']:
        """
        Returns all member junctions, whether directly or indirectly within this port
        """
        ret_val = OrderedSet()
        if self.is_composite():
            for member, _ in self.get_member_junctions().values():
                ret_val |= member.get_all_member_junctions(True)
        elif add_self:
            ret_val.add(self)
        return ret_val

    def get_all_member_junctions_with_names(self, add_self: bool) -> Dict[Tuple[str], Tuple['Junction', bool]]:
        """
        Returns all member junctions, whether directly or indirectly within this port
        """
        def _get_all_member_junctions_with_names(junction: 'Junction', add_self: bool, base_names: Tuple[str] = (), outer_reverse: bool = False) -> Dict[Tuple[str], 'Junction']:
            ret_val = OrderedDict()
            if junction.is_composite():
                for name, (member, reverse) in junction.get_member_junctions().items():
                    ret_val.update(_get_all_member_junctions_with_names(member, True, base_names + (name,), outer_reverse ^ reverse))
            elif add_self:
                ret_val[base_names] = (junction, outer_reverse)
            return ret_val
        return _get_all_member_junctions_with_names(self, add_self)

    def get_lhs_name(self, back_end: 'BackEnd', target_namespace: 'Module', allow_implicit: bool=True) -> Optional[str]:
        return self.get_net_type().get_lhs_name(self, back_end, target_namespace, allow_implicit)

    def get_rhs_expression(self, back_end: 'BackEnd', target_namespace: 'Module', default_type: Optional[NetType] = None, outer_precedence: Optional[int] = None, allow_expression: bool = True) -> Tuple[str, int]:
        if not self.is_specialized():
            assert default_type is not None
            return default_type.get_unconnected_value(back_end), 0
        else:
            return self.get_net_type().get_rhs_expression(self, back_end, target_namespace, outer_precedence, allow_expression)


class Port(Junction):

    def __init__(self, net_type: Optional[NetType] = None, parent_module: 'Module' = None, *, keyword_only: bool = False):
        super().__init__(net_type, parent_module, keyword_only=keyword_only)
        self._auto = False # Set to true for auto-ports

    def is_deleted(self) -> bool:
        """
        Returns True if the port (an optional auto-port with no driver) got deleted from the interface
        """
        return False
    
    def get_default_name(self, scope: object) -> str:
        if scope is not self.get_parent_module()._impl.parent:
            raise SyntaxErrorException(f"Can't generate default name for port except for its parent scope. Did you end up referencing a port in a different scope?")
        return f"{self.get_parent_module()._impl.get_name()}{MEMBER_DELIMITER}{first(self.get_interface_names())}"

    def add_interface_name(self, name: str) -> None:
        assert self._parent_module is not None
        scope_table = self._parent_module._impl.netlist.symbol_table[self._parent_module]
        scope_table.add_hard_symbol(self, name)
        for member_name, (member_junction, _) in self.get_member_junctions().items():
            member_junction.add_interface_name(f"{name}{MEMBER_DELIMITER}{member_name}")

    def get_interface_names(self) -> str:
        assert self._parent_module is not None
        scope_table = self._parent_module._impl.netlist.symbol_table[self._parent_module]
        return scope_table.get_hard_names(self)

    def del_interface_name(self, name: str) -> None:
        assert self._parent_module is not None
        self._parent_module._impl.netlist.symbol_table[self._parent_module].del_hard_symbol(self, name)
        for member_name, (member_junction, _) in self.get_member_junctions().items():
            member_junction.del_interface_name()






class InputPort(Port):
    @classmethod
    def generate_junction_ref(cls, back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return "input"
    @classmethod
    def get_member_junction_kind(cls, is_reversed: bool) -> Type:
        if is_reversed:
            return Output
        else:
            return Input
    @classmethod
    def is_instantiable(cls) -> bool:
        return True
    junction_kind: str = "input"

    def set_source(self, source: Any, scope: 'Module') -> None:
        """
        We don't allow assignment from 'inside'
        """
        if self.get_parent_module() is scope:
            raise SyntaxErrorException(f"Can't assign to input port {self} from within its module")
        super().set_source(source, scope)



class OutputPort(Port):

    def __init__(self, net_type: Optional[NetType] = None, parent_module: 'Module' = None):
        super().__init__(net_type, parent_module)
        self.rhs_expression: Optional[Tuple[str, int]] = None # Filled-in by the parent_module during the 'generation' phase to contain the expression for the right-hand-side value, if inline expressions are supported for this port.

    @classmethod
    def generate_junction_ref(cls, back_end: 'BackEnd') -> str:
        assert back_end.language == "SystemVerilog"
        return "output"
    @classmethod
    def get_member_junction_kind(cls, is_reversed: bool) -> Type:
        if is_reversed:
            return Input
        else:
            return Output
    @classmethod
    def is_instantiable(cls) -> bool:
        return True
    junction_kind: str = "output"

    def has_driver(self, allow_non_auto_inputs: bool = False) -> bool:
        return True

    def is_deleted(self) -> bool:
        """
        Returns True if the port (an optional auto-port with no driver) got deleted from the interface
        """
        return False

    def set_source(self, source: Any, scope: 'Module') -> None:
        """
        We don't allow assignment from 'outside'
        """
        if self.get_parent_module() is not scope:
            raise SyntaxErrorException(f"Can't assign to output port {self} from outside its module")
        super().set_source(source, scope)

    '''
    class OutputSliceGetter(object):
        def __ilshift__(self, other: Any) -> 'Junction':
            return other


    def __getitem__(self, key: Any) -> Any:
        # Since we don't allow reading of outputs, we will have to return a special value that only supports the "<<=" notation
        return Output.OutputSliceGetter()
    '''

# Wires are special ports that only exist within a Module and aren't part of the interface.
# These special ports can be created within the body of a Module and can be checked/assigned within simulate.
class WireJunction(Junction):

    def __init__(self, net_type: Optional[NetType] = None, parent_module: 'Module' = None):
        from .netlist import Netlist
        if parent_module is None:
            parent_module = Netlist.get_current_scope()
        super().__init__(net_type, parent_module)
        if parent_module is not None:
            parent_module._impl.register_wire(self)
        self.rhs_expression: Optional[Tuple[str, int]] = None # Filled-in by the parent_module during the 'generation' phase to contain the expression for the right-hand-side value, if inline expressions are supported for this port.

    def get_default_name(self, scope: object) -> str:
        return "unnamed_wire"

    @classmethod
    def is_instantiable(cls) -> bool:
        return True

    def has_driver(self, allow_non_auto_inputs: bool = False) -> bool:
        return True

    @classmethod
    def get_member_junction_kind(cls, is_reversed: bool) -> Type:
        return Wire

    junction_kind: str = "wire"

class ScopedPort(JunctionBase):
    """
    A Port wrapper that can be used as an alias for a port within a 'with' clause:

    with master_clk as clk:
        something <<= Reg(another_thing)

    Here, master_clk becomes a ScopedPort instance for the duration of the with block.
    Since Python doesn't really get rid of locals introduces in 'with' blocks, master_clk
    as a name still exists within 'locals' after __exit__ is called. What ScopedPort does
    is it disallows automatic binding after __exit__ is executed. This way, while the name
    technically still exists, and can be used explicitly, it won't automatically bind to
    ports anymore. 
    """
    attributes = ("_real_junction")
    def __init__(self, real_junction: JunctionBase):
        self._real_junction = real_junction
    def _update_real_port(self, real_junction: Optional[JunctionBase]):
        self._real_junction = real_junction
    def __setattr__(self, name, value):
        if name in ScopedPort.attributes:
            super().__setattr__(name, value)
        else:
            if self._real_junction is None:
                raise AttributeError
            self.get_underlying_junction().__setattr__(name, value)
    def __getattr__(self, name: str) -> Any:
        if self._real_junction is None:
            raise AttributeError
        return self.get_underlying_junction().__getattribute__(name)
    def get_underlying_scoped_port(self) -> 'ScopedPort':
        """
        Recurses through the scoped port hierarchy and returns the bottom-most scoped port
        """
        try:
            return self._real_junction.get_underlying_scoped_port()
        except AttributeError:
            return self
    def get_underlying_junction(self) -> Optional['Junction']:
        if self._real_junction is None:
            return None
        return self._real_junction.get_underlying_junction()
    def allow_auto_bind(self) -> bool:
        """
        Determines if auto-port binding to this port is allowed.
        Defaults to True, but for scoped ports, get set to False
        upon __exit__
        """
        if self._real_junction is None:
            return False
        return self.get_underlying_junction().allow_auto_bind()
    def allow_bind(self) -> bool:
        """
        Determines if port binding to this port is allowed.
        Defaults to True, but for scoped ports, get set to
        False to disallow shananingans, like this:
            with my_port as x:
                x <<= 3
        """
        return False

class JunctionRef(object):
    """
    A small class that can store references to ports while circumventing the __setattr__ logic in the storer that might attempt to bind ports upon assignment
    """
    def __init__(self, junction: Junction):
        self.junction = junction
    def get_underlying_junction(self) -> Optional['Junction']:
        return self.junction.get_underlying_junction()

def junction_ref(junction: Optional[Junction]) -> Optional[JunctionRef]:
    if junction is None:
        return None
    return JunctionRef(junction)




_JunctionInstances = {}

def create_junction_type(junction_type: 'JunctionBase', net_type: Optional[NetTypeMeta] = None, extra_bases: Optional[Sequence[type]] = None, extra_dict: Optional[Dict] = None) -> 'type':
    # We never cache types with extra dictionaries.
    if extra_dict is None:
        try:
            return _JunctionInstances[(junction_type, net_type)]
        except KeyError:
            pass
    if net_type is None:
        bases = (junction_type, )
        type_name = f"None.{junction_type.__name__}"
    else:
        bases = (junction_type, net_type)
        type_name = f"{net_type.__name__}.{junction_type.__name__}"
    if extra_bases is not None:
        bases += extra_bases

    typed_junction_type = type(type_name, bases, {} if extra_dict is None else extra_dict)

    if extra_dict is None:
        _JunctionInstances[(junction_type, net_type)] = typed_junction_type
    return typed_junction_type

def create_junction(junction_type: 'JunctionBase', net_type: Optional[NetTypeMeta] = None, *args, **kwargs) -> 'Junction':
    typed_junction_type = create_junction_type(junction_type, net_type)
    ret_val = typed_junction_type(net_type, *args, **kwargs)
    return ret_val

def Input(net_type: Optional[NetTypeMeta] = None, *args, **kwargs) -> InputPort:
    return create_junction(InputPort, net_type, *args, **kwargs)

def Output(net_type: Optional[NetTypeMeta] = None, *args, **kwargs) -> OutputPort:
    return create_junction(OutputPort, net_type, *args, **kwargs)

def Wire(net_type: Optional[NetTypeMeta] = None, *args, **kwargs) -> WireJunction:
    return create_junction(WireJunction, net_type, *args, **kwargs)

