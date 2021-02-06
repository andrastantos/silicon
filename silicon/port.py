from typing import Tuple, Dict, Optional, Set, Any, Type, Sequence, Union, Callable

from .net_type import NetType, KeyKind
from .tracer import no_trace, NoTrace
from .ordered_set import OrderedSet
from .exceptions import SyntaxErrorException, SimulationException
from .utils import convert_to_junction, is_junction, is_input_port, is_output_port, is_wire, get_caller_local_junctions, is_junction_member, BoolMarker, is_module, implicit_adapt, MEMBER_DELIMITER
from .port import KeyKind
from collections import OrderedDict
from enum import Enum

class JunctionBase(object):
    pass

class EdgeType(Enum):
    NoEdge = 0
    Positive = 1
    Negative = 2
    Undefined = 3

class Junction(JunctionBase):
    
    def __init__(self, net_type: Optional[NetType] = None, parent_module: 'Module' = None, *, keyword_only: bool = False):
        assert parent_module is None or is_module(parent_module)
        from .module import Module
        self.source: Optional['Port'] = None
        self.sinks: Set[Junction] = OrderedSet()
        assert parent_module is None or isinstance(parent_module, Module)
        self._parent_module = parent_module
        self._in_attr_access = False
        self.interface_name = None # set to a string showing the interface name when the port/wire is assigned to a Module attribute (in Module.__setattr__)
        self.keyword_only = keyword_only
        self.raw_input_map = [] # contains section inputs before Concatenator or MemberSetter can be created.
        self._allow_auto_bind = True
        self._in_with_block = False
        self._member_junctions = OrderedDict() # Contains members for struct/interfaces/vectors
        self._parent_junction = None # Reverences back to the container for struct/interface/vector members
        self._net_type = None
        if net_type is not None:
            if not isinstance(net_type, NetType):
                raise SyntaxErrorException(f"Net type for a port must be a subclass of NetType. (Did you forget to construct an instance?)")
            self.set_net_type(net_type)
        if self._parent_module is not None:
            self.set_context(self._parent_module._impl.active_context())
        else:
            self.set_context(None)

    def __str__(self) -> str:
        ret_val = self.get_diagnostic_name()
        if self.is_typeless():
            return ret_val
        ret_val += ": " + str(self.get_net_type())
        if not hasattr(self, "_xnet") or self._xnet is None:
            return ret_val
        ret_val += f" = {self._xnet.sim_state.value}"
        return ret_val

    def get_underlying_junction(self) -> 'Junction':
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
        self._parent_module = parent_module
        self.set_context(self._parent_module._impl.active_context())
        # Recurse into members
        for member_junction, _ in self.get_member_junctions().values():
            member_junction.set_parent_module(parent_module)

    def get_parent_module(self) -> Optional['Module']:
        return self._parent_module

    def finalize_slices(self) -> None:
        if len(self.raw_input_map) > 0:
            assert not self.is_composite() # We can only generate slices of non-compound types (TODO: what about vectors???)
            self.concatenator = self.get_net_type().create_member_setter()
            self.set_source(self.concatenator.output_port)
            for (key, real_junction) in self.raw_input_map:
                self.concatenator.add_input(key, real_junction)
            self.raw_input_map = [] # Prevent re-creation of Concatenator
            # If the concatenator was created outside the normal body context (during type determination)
            # We'll have to make sure it's properly registered
            if self.active_context() is None:
                assert False, "I DONT THINK THIS SHOULD HAPPEN!!!!!"
                self.concatenator.freeze_interface()
                self.concatenator._body()

    def set_net_type(self, net_type: Optional[NetType]) -> None:
        # Only allow the net_type to be set if it's not set yet, or if it's an abstract type (that is to allow specialization of a port)
        # TODO: For now we also allow the net_type to be set from one abstract type to another one, but that can probably be tightened later
        #       For example, we could say that the new prot type must be an instance of the old port type...
        if self._net_type == net_type:
            return
        assert not self.is_specialized()
        self._net_type = net_type
        if net_type is not None:
            net_type.setup_junction(self)
        # We need to ensure port type compatibility with all sinks/source
        if self.is_specialized():
            for sink in self.sinks:
                if sink.is_specialized():
                    # Insert adaptor if needed (through set_source)
                    sink.set_source(self)
            if self.source is not None and self.source.is_specialized():
                source = self.source
                self.set_source(source)

    def has_driver(self, allow_non_auto_inputs: bool = False) -> bool:
        """
        Returns True if the port can possibly have a driver (source-chain ends in a wire or an Output)
        """
        # For compound types, we can't easily answer this question. It's the individual members that may or may not have drivers.
        if self.is_composite():
            return False
        junction = self
        while junction.source is not None:
            if is_input_port(junction.source) and (allow_non_auto_inputs or junction.source._auto):
                junction = junction.source
            else:
                return True
        return False

    def get_net_type(self) -> Optional[NetType]:
        return self._net_type
    def is_typeless(self) -> bool:
        if "_net_type" not in self.__dict__:
            return True
        return self._net_type is None
    def is_specialized(self) -> bool:
        """
        Returns True if the port has a non-abstract type.
        """
        if self.is_typeless():
            return False
        return not self.get_net_type().is_abstract()
    def is_abstract(self) -> bool:
        """
        Returns True if the port has an abstract type, or no type at all
        """
        if self.is_typeless():
            return True
        return self.get_net_type().is_abstract()

    def set_source(self, source: 'Junction') -> None:
        old_source = f"{id(self.source):x}" if self.source is not None else "--NONE--" 
        def del_source() -> None:
            """
            Removes the potentially existing binding between this port and its source
            """
            #assert not self.is_composite() <-- we call this on composites now as well, but only after all the members are patched up. So it's OK to only deal with the top-level.
            if self.source is not None:
                self.source.sinks.remove(self)
            self.source = None

        # If both ports have types, make sure they're compatible.
        if not source.is_typeless() and not self.is_typeless():
            from .utils import adapt
            # Insert adaptor if needed
            old_junction = source
            # ... but first figure out into which context the adaptor should be inserted (if any).
            # There are four possibilities:
            # 1. An input of a module is assigned to an output of the same -> insert into the parent scope
            if self.get_parent_module() is source.get_parent_module():
                scope = self.get_parent_module()
            # 2. Two ports feed one another on the same hierarchy level -> insert into enclosing scope
            elif self.get_parent_module()._impl.parent is source.get_parent_module()._impl.parent:
                scope = self.get_parent_module()._impl.parent
            # 3. Outer input feeds inner input -> insert into outer scope
            elif self.get_parent_module() is source.get_parent_module()._impl.parent:
                scope = source.get_parent_module()._impl.parent
            # 4. Inner output feeds outer output -> insert into outer scope
            elif self.get_parent_module()._impl.parent is source.get_parent_module():
                scope = self.get_parent_module()._impl.parent
            else:
                raise SyntaxErrorException(f"Can't set {source} as the source of {self}. Most likely reason is that they skip hierarchy levels.")
            assert scope is not None
            assert is_module(scope)
            from .module import Module
            with Module._parent_modules.push(scope):
                source = implicit_adapt(source, self.get_net_type())
                # If an adaptor was created, we'll have to make sure it's properly registered.
                if self.active_context() is None:
                    if source is not old_junction:
                        adaptor = source.get_parent_module()
                        adaptor._impl.freeze_interface()
                        adaptor._impl._body(trace=False)
            if source is not old_junction and old_junction.get_parent_module()._impl.has_explicit_name:
                with scope._impl._inside:
                    naming_wire = Wire(source.get_net_type(), source.get_parent_module()._impl.parent)
                    naming_wire.local_name = old_junction.interface_name # This creates duplicates of course, but that will be resolved later on
                    naming_wire.bind(source)
        # At this point source is compatible with us. The actual binding however will have to be port-wise for compoud types and recursively
        if self.is_composite():
            if source.is_typeless():
                # It's possible that the source doesn't quite yet have a type (for example the result of a Select on a Struct).
                # In that case, we back-propagate the sinks' type to the source.
                sinks = source.get_all_sinks()
                for sink in sinks:
                    if not sink.is_typeless() and self.get_net_type() != sink.get_net_type():
                        raise SyntaxErrorException(f"A sink if junction {source} ({sink}) is of the wrong type. All sinks should have type {source.get_net_type()}.")
                source.set_net_type(self.get_net_type())
            for member_name, (member_junction, reversed) in self.get_member_junctions().items():
                if reversed:
                    source.get_member_junctions()[member_name][0].set_source(member_junction)
                else:
                    member_junction.set_source(source.get_member_junctions()[member_name][0])

        del_source()
        self.source = source
        assert self not in source.sinks
        source.sinks.add(self)
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
        if self.is_typeless():
            raise SyntaxErrorException(f"Can't iterate through the elements of a typeless port {self}")
        if self.is_abstract():
            raise SyntaxErrorException(f"Can't iterate through the elements of an abstract port {self}")
        return self.get_net_type().get_iterator(self)
    
    def __len__(self) -> int:
        if self.is_typeless():
            raise SyntaxErrorException(f"Can't determine the length of a typeless port {self}")
        if self.is_abstract():
            raise SyntaxErrorException(f"Can't determine the length of an abstract port {self}")
        net_type = self.get_net_type()
        if not hasattr(net_type, "get_length"):
            raise SyntaxErrorException(f"Net {self} of type {net_type} doesn't support 'len'")
        return net_type.get_length()

    
    def __getitem__(self, key: Any) -> Any:
        if self.active_context() == "simulation":
            return self.get_net_type().get_slice(key, self)
        else:
            from .member_access import MemberGetter
            return MemberGetter(self, [(key, KeyKind.Index)])
    
    def __setitem__(self, key: Any, value: Any) -> None:
        if is_junction_member(value) and value.get_parent_junction() is self:
            return
        if hasattr(self.get_net_type(), "set_member_access"):
            return self.get_net_type().set_member_access([(key, KeyKind.Index)], value, self)
        raise TypeError()
    
    def __delitem__(self, key: Any) -> None:
        # I'm not sure what this even means in this context
        raise TypeError()

    
    def __getattr__(self, name: str) -> Any:
        if "_member_junctions" in dir(self) and name in self._member_junctions:
            return self._member_junctions[name][0]
        if not self.is_typeless() and hasattr(self.get_net_type(), "get_junction_member"):
            return self.get_net_type().get_junction_member(self, name)
        raise AttributeError
    
    def __setattr__(self, name: str, value: Any) -> None:
        if "_member_junctions" in dir(self) and name in self._member_junctions:
            if value is self._member_junctions[name][0]:
                return
            self._member_junctions[name][0] <<= value
        if not self.is_typeless() and hasattr(self.get_net_type(), "set_junction_member"):
            if self.get_net_type().set_junction_member(self, name, value):
                return
        super().__setattr__(name, value)

    def allow_bind(self) -> bool:
        """
        Determines if binding to this junction is allowed.
        Defaults to True, but for scoped junctions, get set to 
        False to disallow shananingans, like this:
            with my_port as x:
                x <<= 3
        """
        return True

    def allow_auto_bind(self) -> bool:
        """
        Determines if auto-binding to this junction is allowed.
        Defaults to True, but for scoped ports, get set to False
        upon __exit__
        """
        return self._allow_auto_bind

    
    def __enter__(self) -> 'Junction':
        assert not self._in_with_block
        self._in_with_block = True
        self._allow_auto_bind = True
        self._scoped_port = ScopedPort(self)
        self._junctions_before_scope = get_caller_local_junctions(3)
        return self._scoped_port

    
    def __exit__(self, exception_type, exception_value, traceback):
        assert self._in_with_block
        self._in_with_block = False
        self._allow_auto_bind = False
        # TODO: This can be perf optimized: we iterate twice, once in get_caller_local_junctions and once here...
        junctions_after_scope = get_caller_local_junctions(3)
        found = False
        for name, junction in junctions_after_scope.items():
            if junction is self._scoped_port:
                old_junction = self._junctions_before_scope.get(name, None)
                if old_junction is not None and found:
                    raise SyntaxErrorException(f"This is not supported: scoped port {self} got assigned to multiple already existing local net references. Can't restore originals.")
                self._scoped_port._update_real_port(old_junction)
                found = True
        junction = None
        del junctions_after_scope
        del self._junctions_before_scope

    def is_inside(self) -> bool:
        return self.get_parent_module()._impl.is_inside()

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
        module_name = self.get_parent_module()._impl.get_diagnostic_name(False)
        if self.interface_name is None:
            name = "<unknown>"
        else:
            name = self.interface_name
        name = module_name + FQN_DELIMITER + name
        if add_location:
            name += self.get_parent_module()._impl.get_diagnostic_location(" at ")
        return name

    def _binary_op(self, other: Any, gate: 'Module', name: str) -> Any:
        context = self.active_context()
        from .gates import _sim_value
        if context == "simulation":
            return gate.sim_op(self, _sim_value(other))
        elif context == "elaboration":
            return gate(self, other)
        else:
            sup = super()
            return getattr(sup, name)(other)

    def _rbinary_op(self, other: Any, gate: 'Module', name: str) -> Any:
        context = self.active_context()
        if context == "simulation":
            return gate.sim_op(other, self.sim_value)
        elif context == "elaboration":
            return gate(other, self)
        else:
            sup = super()
            return getattr(sup, name)(other)

    def _unary_op(self, gate: 'Module', name: str) -> Any:
        context = self.active_context()
        if context == "simulation":
            return gate.sim_op(self)
        elif context == "elaboration":
            return gate(self)
        else:
            sup = super()
            return getattr(sup, name)()

    def _ninput_op(self, other: Any, gate: 'Module', name: str) -> Any:
        context = self.active_context()
        if context == "simulation":
            return gate.sim_op(other, self.sim_value)
        elif context == "elaboration":
            return gate(self, other)
        else:
            sup = super()
            return getattr(sup, name)(other)

    def _rninput_op(self, other, gate: 'Module', name: str) -> Any:
        context = self.active_context()
        from .gates import _sim_value
        if context == "simulation":
            return gate.sim_op(self, _sim_value(other))
        elif context == "elaboration":
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
    
    def __floordiv__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __mod__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __divmod__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __pow__(self, other: Any, modulo = None) -> Any:
        assert False, "FIXME: implement!"
    
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
    
    def __truediv__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"

    
    def __radd__(self, other: Any) -> Any:
        from .gates import sum_gate as gate
        return self._rninput_op(other, gate, "__radd__")
    
    def __rsub__(self, other: Any) -> Any:
        from .gates import sub_gate as gate
        return self._rbinary_op(other, gate, "__rsub__")
    
    def __rmul__(self, other: Any) -> Any:
        from .gates import prod_gate as gate
        return self._rninput_op(other, gate, "__rmul__")
    
    def __rtruediv__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __rfloordiv__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __rmod__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __rdivmod__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __rpow__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
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
    """
    
    def __iadd__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __isub__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __imul__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __idiv__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __itruediv__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __ifloordiv__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __imod__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __ipow__(self, other: Any, modulo = None) -> Any:
        assert False, "FIXME: implement!"
    
    def __ilshift__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __irshift__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __iand__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __ixor__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    
    def __ior__(self, other: Any) -> Any:
        assert False, "FIXME: implement!"
    """

    
    def __ilshift__elab(self, other: Any) -> 'Junction':
        try:
            junction_value = convert_to_junction(other)
            if junction_value is None:
                # We couldn't create a port out of the value:
                raise SyntaxErrorException(f"couldn't bind port to value '{other}'.")
        except Exception as ex:
            raise SyntaxErrorException(f"couldn't bind port to value '{other}' with exception '{ex}'")
        # assignment-style binding is only allowed for outputs (on the inside) and inputs (on the outside)
        if self.is_inside():
            if is_input_port(self):
                raise SyntaxErrorException(f"Can't assign to {self.junction_kind} port '{self.get_diagnostic_name()}' from inside the module")
        else:
            if not is_input_port(self):
                raise SyntaxErrorException(f"Can't assign to {self.junction_kind} port '{self.get_diagnostic_name()}' from outside the module")
        if self.source is not None:
            raise SyntaxErrorException(f"Can't assign to {self.get_diagnostic_name()}: it already has a source")
        self.bind(junction_value)
        return self

    def __ilshift__sim(self, other: Any) -> 'Junction':
        if self.is_composite():
            if other is not None and other.source is not None and (not isinstance(other, Junction) or self.get_net_type() != other.get_net_type()):
                raise SimulationException(f"Assignment to compound types during simulation is only supported between identical net types")
            # If something is connected to an otherwise unconnected port, we should support that.
            if other is None or other.source is None:
                for self_member in self.get_all_member_junctions(add_self=False):
                    self_member._set_sim_val(None)
            else:
                for self_member, other_member in zip(self.get_all_member_junctions(add_self=False), other.get_all_member_junctions(add_self=False)):
                    self_member._set_sim_val(other_member)
        else:
            self._set_sim_val(other)
        return self

    def __ilshift__none(self, other: Any) -> 'Junction':
        return super().__ilshift__(other)

    def __ilshift__impl(self, other: Any) -> 'Junction':
        return self.__ilshift__none(other)

    def __ilshift__(self, other: Any) -> 'Junction':
        return self.__ilshift__impl(other)

    def _set_sim_val(self, value: Any, when: Optional[int] = None) -> None:
        assert not self.is_composite(), "Simulator should never set the value of compound types"
        # using hasattr instead of is_junction to speed up simulation. It also catches PortSlices not just Ports
        if hasattr(value, "sim_value"):
            new_sim_value = value.sim_value
        else:
            new_sim_value = sim_const(value)

        assert self._xnet.source is self or self._xnet.source is None
        if self._xnet.source is self:
            self._xnet.sim_state.sim_context.schedule_value_change(self._xnet, new_sim_value, when)

    
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
        return self._unary_op(gate, "__invert__")

    
    def __complex__(self) -> Any:
        assert False, "FIXME: implement!"
    
    def __int__(self) -> Any:
        assert False, "FIXME: implement!"
    
    def __long__(self) -> Any:
        assert False, "FIXME: implement!"
    
    def __float__(self) -> Any:
        assert False, "FIXME: implement!"

    
    def __oct__(self) -> Any:
        assert False, "FIXME: implement!"
    
    def __hex__(self) -> Any:
        assert False, "FIXME: implement!"

    '''
    
    def __index__(self) -> Any:
        assert False, "FIXME: implement!"
    '''

    
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

    def __hash__(self):
        return id(self)

    def set_context(self, context: str) -> None:
        self._context = context
        if context is None:
            self.__ilshift__impl = self.__ilshift__none
        elif context == "simulation":
            self.__ilshift__impl = self.__ilshift__sim
        elif context == "elaboration":
            self.__ilshift__impl = self.__ilshift__elab
        else:
            assert False
        for member_junction, _ in self._member_junctions.values():
            member_junction.set_context(context)

    def active_context(self) -> str:
        return self._context

    def adapt_to(self, output_type: 'NetType', implicit: bool) -> 'Junction':
        return self.get_net_type().adapt_to(output_type, self, implicit)


    def set_interface_name(self, name: str) -> None:
        self.interface_name = name
        for member_name, (member_junction, _) in self.get_member_junctions().items():
            member_junction.set_interface_name(f"{self.interface_name}{MEMBER_DELIMITER}{member_name}")


    ############################################
    # Compund type support
    ############################################
    @classmethod
    def get_member_junction_kind(cls, is_reversed: bool) -> Type:
        raise NotImplementedError

    def create_member_junction(self, name: str, net_type: 'NetType', reversed: bool) -> None:
        assert not self.is_typeless(), "Can't add members to a typeless port. In fact, create_member_junction should only be called from the junctions type."
        junction_type = self.get_member_junction_kind(reversed)
        member = junction_type(net_type, self.get_parent_module())
        if self.interface_name is not None:
            member.set_interface_name(f"{self.interface_name}{MEMBER_DELIMITER}{name}")
        member._parent_junction = self
        self._member_junctions[name] = [member, reversed]
    
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

    def convert_from(self, input: 'Junction') -> None:
        if self.get_net_type() is input.get_net_type():
            self <<= input
        else:
            self.from_number(input.to_number())

    def get_lhs_name(self, back_end: 'BackEnd', target_namespace: 'Module', allow_implicit: bool=True) -> Optional[str]:
        return self.get_net_type().get_lhs_name(self, back_end, target_namespace, allow_implicit)

    def get_rhs_expression(self, back_end: 'BackEnd', target_namespace: 'Module', default_type: Optional[NetType] = None, outer_precedence: Optional[int] = None) -> Tuple[str, int]:
        if self.is_typeless():
            assert default_type is not None
            return default_type.get_unconnected_value(back_end), 0
        else:
            return self.get_net_type().get_rhs_expression(self, back_end, target_namespace, outer_precedence)


class Port(Junction):
    
    def __init__(self, net_type: Optional[NetType] = None, parent_module: 'Module' = None, *, keyword_only: bool = False):
        super().__init__(net_type, parent_module, keyword_only=keyword_only)
        self._auto = False # Set to true for auto-ports

    def is_deleted(self) -> bool:
        """
        Returns True if the port (an optional auto-port with no driver) got deleted from the interface
        """
        return False







class Input(Port):
    
    def bind(self, other_junction: Junction) -> None:
        assert is_junction(other_junction), "Can only bind to junction"
        assert self.get_parent_module() is not None, "Can't bind free-standing junction"
        assert other_junction.get_parent_module() is not None, "Can't bind to free-standing junctio"
        assert not self.is_inside() or not other_junction.is_inside() or self.get_parent_module() is other_junction.get_parent_module(), "INTERNAL ERROR: how can it be that we're inside two modules at the same time?"
        if not self.allow_bind():
            raise SyntaxErrorException(f"Can't bind to port {self}: Port doesn't allow binding")
        if not other_junction.allow_bind():
            raise SyntaxErrorException(f"Can't bind port {other_junction}: Port doesn't allow binding")
        if bool(self.is_inside()) == bool(other_junction.is_inside()):
            # We're either outside of both modules, or we're inside a single module: connect inputs to outputs only
            assert not is_input_port(other_junction), "Cannot bind input to input within the same hierarchy level"
        else:
            # We're inside one of the modules and outside the other: connect inputs to inputs only
            # Actually that's not true: the other port could be either an input or an output
            #assert is_input_port(other_junction), "Cannot bind input to output through hierarchy levels"
            pass
        if self.is_inside():
            other_junction.set_source(self)
        else:
            self.set_source(other_junction)
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




class Output(Port):
    
    def __init__(self, net_type: Optional[NetType] = None, parent_module: 'Module' = None):
        super().__init__(net_type, parent_module)
        self.rhs_expression: Optional[Tuple[str, int]] = None # Filled-in by the parent_module during the 'generation' phase to contain the expression for the right-hand-side value, if inline expressions are supported for this port.

    def bind(self, other_junction: Junction) -> None:
        assert is_junction(other_junction), "Can only bind to junction"
        assert self.get_parent_module() is not None, "Can't bind free-standing junction"
        assert other_junction.get_parent_module() is not None, "Can't bind to free-standing junction"
        assert not self.is_inside() or not other_junction.is_inside() or self.get_parent_module() is other_junction.get_parent_module(), "INTERNAL ERROR: how can it be that we're inside two modules at the same time?"
        if not self.allow_bind():
            raise SyntaxErrorException(f"Can't bind to port {self}: Port doesn't allow binding")
        if not other_junction.allow_bind():
            raise SyntaxErrorException(f"Can't bind port {other_junction}: Port doesn't allow binding")
        if self.is_inside() == other_junction.is_inside():
            # We're either outside of both modules, or we're inside a single module: connect inputs to outputs only
            assert not is_output_port(other_junction), "Cannot bind output to output within the same hierarchy level"
        else:
            # We're inside one of the modules and outside the other: connect inputs to inputs only
            assert not is_input_port(other_junction), "Cannot bind output to input through hierarchy levels"
        if self.is_inside():
            self.set_source(other_junction)
        else:
            other_junction.set_source(self)
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

    def adapt_from(self, input_type: 'NetType', implicit: bool) -> 'Junction':
        return self.get_net_type().adapt_from(input_type, self, implicit)

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
class Wire(Junction):
    
    def __init__(self, net_type: Optional[NetType] = None, parent_module: 'Module' = None):
        from .module import Module
        if parent_module is None:
            if not Module._parent_modules.is_empty():
                parent_module = Module._parent_modules.top()
        super().__init__(net_type, parent_module)
        parent_module._impl.register_wire(self)
        self.rhs_expression: Optional[Tuple[str, int]] = None # Filled-in by the parent_module during the 'generation' phase to contain the expression for the right-hand-side value, if inline expressions are supported for this port.
        self.local_name: Optional[str] = None

    def bind(self, other_junction: Junction) -> None:
        assert is_junction(other_junction), "Can only bind to junction"
        assert self.get_parent_module() is not None, "Can't bind free-standing junction"
        assert other_junction.get_parent_module() is not None, "Can't bind to free-standing junction"
        assert not self.is_inside() or not other_junction.is_inside() or self.get_parent_module() is other_junction.get_parent_module(), "INTERNAL ERROR: how can it be that we're inside two modules at the same time?"
        if not self.allow_bind():
            raise SyntaxErrorException(f"Can't bind to wire {self}: Wire doesn't allow binding")
        if not other_junction.allow_bind():
            raise SyntaxErrorException(f"Can't bind net {other_junction}: Net doesn't allow binding")
        if self.is_inside() == other_junction.is_inside():
            # We're either outside of both modules, or we're inside a single module: connect inputs to outputs only
            assert not is_output_port(other_junction), "Cannot bind output to output within the same hierarchy level"
        else:
            # We're inside one of the modules and outside the other: connect inputs to inputs only
            assert not is_input_port(other_junction), "Cannot bind output to input through hierarchy levels"
        if self.is_inside():
            self.set_source(other_junction)
        else:
            other_junction.set_source(self)
    @classmethod
    def is_instantiable(cls) -> bool:
        return True

    def has_driver(self, allow_non_auto_inputs: bool = False) -> bool:
        return True

    def adapt_from(self, input_type: 'NetType', implicit: bool) -> 'Junction':
        return self.get_net_type().adapt_from(input_type, self, implicit)

    @classmethod
    def get_member_junction_kind(cls, is_reversed: bool) -> Type:
        return Wire

    junction_kind: str = "wire"

class ScopedPort(JunctionBase):
    attributes = ("_real_junction")
    def __init__(self, real_junction: Union[Junction, 'MemberGetter']):
        self._real_junction = real_junction
    def _update_real_port(self, real_junction: Optional[Union[Junction, 'MemberGetter']]):
        self._real_junction = real_junction
    def __setattr__(self, name, value):
        from .utils import is_junction_member
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
    def get_underlying_junction(self) -> 'Junction':
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
        from .utils import is_junction_member
        if is_junction_member(self._real_junction):
            return self._real_junction.allow_auto_bind()
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
    def get_underlying_junction(self) -> 'Junction':
        return self.junction.get_underlying_junction()

class AutoInput(Input):
    """
    An input port variant that supports automatic binding to a set of named nets in the enclosing namespace.
    """
    def __init__(self, net_type: Optional[NetType] = None, parent_module: 'Module' = None, *, keyword_only: bool = False, auto_port_names: Union[str, Sequence[str]], optional: bool = True):
        super().__init__(net_type=net_type, parent_module=parent_module, keyword_only=keyword_only)
        if isinstance(auto_port_names, str):
            auto_port_names = (auto_port_names,)
        self._auto_port_names = tuple(auto_port_names)
        self._optional = optional
        self._candidate = None
        self._auto = True
    def find_cadidates(self):
        assert self.get_parent_module() is not None
        self._candidate = junction_ref(self.get_parent_module()._impl.get_auto_port_to_bind(self._auto_port_names))
    def auto_bind(self):
        # If someone bound to this port, let's not override that
        if self.source is not None:
            return
        if self._candidate is None and not self._optional:
            raise SyntaxErrorException(f"Can't auto-connect port {self.get_diagnostic_name()}: none of the names {self._auto_port_names} could be found in the enclosing module")
        if self._candidate is not None:
            self.set_source(self._candidate.junction)
    def is_deleted(self) -> bool:
        """
        Returns True if the port (an optional auto-port with no driver) got deleted from the interface
        """
        return not self.has_driver() and self._optional

    def generate_interface(self, back_end: 'BackEnd', port_name: str) -> Sequence[str]:
        if self.is_typeless():
            assert self.is_deleted()
            return []

        assert back_end.language == "SystemVerilog"
        if not self.is_composite():
            return [f"{self.get_net_type().generate_net_type_ref(self, back_end)} {port_name}"]
        else:
            ret_val = []
            for member_name, (member_junction, _) in self._member_junctions.items():
                ret_val += member_junction.generate_interface(back_end, f"{port_name}{MEMBER_DELIMITER}{member_name}")
            return ret_val
        



def junction_ref(junction: Optional[Junction]) -> Optional[JunctionRef]:
    if junction is None:
        return None
    return JunctionRef(junction)

sim_convert_lookup: Dict[Type, Callable] = {}

def sim_const(value: Any) -> Any:
    if type(value) in sim_convert_lookup:
        return sim_convert_lookup[type(value)](value)
    raise SimulationException(f"Don't know how to convert value {value} of type {type(value)} during simulation")

