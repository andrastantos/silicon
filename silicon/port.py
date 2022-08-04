from abc import abstractmethod
from pydoc import resolve
from typing import Tuple, Dict, Optional, Set, Any, Type, Sequence, Union, Callable
import inspect
from .net_type import NetType, KeyKind, NetTypeMeta
from .tracer import no_trace, NoTrace
from .ordered_set import OrderedSet
from .exceptions import SyntaxErrorException, SimulationException
from .utils import convert_to_junction, is_iterable, is_junction_base, is_junction, is_input_port, is_output_port, is_wire, get_caller_local_junctions, is_junction_member, BoolMarker, is_module, implicit_adapt, MEMBER_DELIMITER, Context, ContextMarker, is_net_type
from .port import KeyKind
from collections import OrderedDict
from enum import Enum


def get_sinks(junction: 'JunctionBase') -> Sequence['Junction']:
    junction = junction.get_underlying_junction()
    net = junction.get_sink_net()
    if net is None:
        return Tuple()
    return net.get_sinks()
class Net(object):
    """
    A net ties together a single source Junction with all its sinks.

    This means that each Net has a well-defined scope (enclosing Module instance),
    but it also means that a Net is not necessarily the full connectivity of that
    wire within the scope.

    As we go through elaboration, we build a set of Nets for the module in question.

    Nets are exclusively managed by their Junctions; the only way to create or modify
    Nets is to call Junction.set_source().

    During the construction process, set_source can identify 5 distinct cases
    as the 'source':
    1. A wire. In that case we know that that's the source.
    2. An output of a sub-module: it is the source
    3. An input of the enclosing module: it is the source
    4. An input of a sub-module: it is *not* the source.
    5. An output of the enclosing module: same as (3). We *know* its not the source.

    For brevity, when I say 'source' is part of a net, I mean 'as a source' and similarly
    for sinks. Note, that a Junction in general can be part of two Nets. One as a source
    and another as a sink.

    For 1,2,3, we'll treat the source as the true source:
    - If source already is part of a Net and sink is not, we add sink to the existing Net.
    - If sink is already part of a net, and source is not, we add the source to the existing
      Net. If the Net already has a source, we err out.
    - If neither are part of nets, we create a net and add them as appropriate
    - If both are part of their respective nets, we'll have to merge the two nets.
      If during that process we end up with multiple sources, err out.

    In case of 4 and 5 we treat both Junctions as sinks:
    - If neither are part of nets, we create one and add them
    - If exactly one of them is part of a net as a sink, add the other as a sink
    - If both are part of nets as sinks, merge the nets. If multiple drivers are the
      result, err out.

    At the end of creating Nets, we can get to a situation, where a Net has more than
    one sinks, but no source. These are treated the same way as if the net has an
    un-typed source.

    After that step, we get to type propagation. Here we do the following:
    1. If none of the junctions in a Net have a type, we'll leave it as-is, maybe
       later on we get to learn more.
    2. If the source doesn't have a type, but some of the sinks do, we can figure out
       (probably with the help of the net types themselves) the most restrictive common
       type. That's going to be the source type, which is assigned, then follow-on to 3.
       If at this point we realize that the Net doesn't even *have* a source, we can
       create a Constant module, which drives it with the 'undefined' value for that type.
    3. If the source has a type, we inspect all the sinks, insert adaptors as needed
       and splinter the net into potentially many nets. During this process, all
       sinks without NetType, get the type of the source (no splitting) and at the
       end each splinter has matching source and sink types.

    Eventually we'll land at a place, where no further progress can be made. If at this
    point we still have junctions (or Nets) with unknown types, we'll err out.

    IMPORTANT!!! Type propagation happens strictly within a scope. That means that
    some nets might later be joined together through XNets (two inputs driven by the
    same source in the enclosing scope for instance), but we don't care about that
    at this stage.

    ALSO IMPORTANT: type propagation and elaboration of sub-modules happens in a
    tit-for-tat fashion and in a depth-first recursive order. This must be so,
    because in many cases the output types of a sub-module are determined from
    their input types during elaboration. What this also means though is that
    nets of different scopes co-exist, and can be partially type-propagated.
    Type-propagation must restrict itself to the same scope. This is not
    a concern for a Net, but it is for the driver of the type-propagation: the
    Module.
    """
    def __init__(self, parent_module: 'Module'):
        self._source: Optional['Junction'] = None
        self._sinks: Set['Junction'] = OrderedSet()
        self._parent_module = parent_module
        self._net_type = None # Cache for net_type. Once set the Net is in immutable.
        self._parent_module._impl.add_net(self)

    def get_source(self) -> Optional['Junction']:
        return self._source
    def set_source(self, source: Optional['JunctionBase']) -> None:
        assert self._net_type is None
        assert is_junction_base(source)
        source = source.get_underlying_junction()
        assert is_junction(source)
        assert self._source in (source, None)
        self._source = source
        source.set_sink_net(self)
    def get_sinks(self) -> Sequence['Junction']:
        return self._sinks
    def get_parent_module(self) -> 'Module':
        return self._parent_module
    def add_sink(self, junction: 'JunctionBase') -> None:
        assert self._net_type is None
        assert is_junction_base(junction)
        junction = junction.get_underlying_junction()
        assert is_junction(junction)
        self._sinks.add(junction)
        old_source_net = junction.get_source_net()
        if old_source_net not in (self, None):
            # We have to merge
            self.merge(old_source_net)
        junction.set_source_net(self)

    def remove_sink(self, junction: 'JunctionBase') -> None:
        """
        Deletes a sink or wire from the net. If junction is not a sink for the net, no changes are made.
        """
        assert self._net_type is None
        junction = junction.get_underlying_junction()
        junction.set_source_net(None)
        try:
            self._sinks.remove(junction)
        except KeyError:
            pass
        # Clean things up if this was the last sink in the Net
        if len(self.get_sinks()) == 0:
            if self.get_source() is not None:
                self.get_source().set_sink_net(None)
            self.get_parent_module().remove_net(self)
        

    def merge(self, net: 'Net'):
        assert self._net_type is None
        assert net._net_type is None
        assert self.get_parent_module() is net.get_parent_module()
        net_source = net.get_source()
        my_source = self.get_source()
        assert net_source is not my_source, "This is impossible since we double-link Nets and Junctions"
        if my_source is None:
            net_source.set_sink_net(None)
            self.set_source(net_source)
        else:
            if net_source is not None:
                raise SyntaxErrorException(f"Net {self} and {net} can't be merged: both have a source")
        for junction in net.get_sinks():
            self._sinks.add(junction)
            junction.set_source_net(self)
        net.set_source(None)
        net._sinks.clear()
        net.get_parent_module()._impl.remove_net(net)

    def get_net_type(self) -> Optional['NetType']:
        """
        Returns (and caches) the net_type of the net, if it can be determined.
        
        For a net to have a net-type, it's source must have a type and all its sinks
        must have the same net-type as well.
        """
        if self._net_type is not None:
            return self._net_type
        source = self.get_source()
        if not source.is_specialized():
            return None
        net_type = source.get_net_type()
        if all(j.get_net_type() is net_type for j in self.get_sinks()):
            self._net_type = net_type
        return self._net_type

    def move_sink(self, junction: 'JunctionBase', new_net: 'Net') -> None:
        """
        Moves junction from one net to another without attempting to merge.
        """
        assert self.net_type is None
        assert new_net._net_type is None
        junction = junction.get_underlying_junction()
        assert junction in self.get_sinks()
        self._sinks.remove(junction)
        self.remove_sink(junction)
        new_net.add_sink(junction)

    def propagate_net_type(self) -> bool:
        """
        Propagates net-type from source to sinks.

        During propagation, implicit adaptors could be inserted, splitting the net into multiple pieces.
        If that happens, the splintered Nets are collected and returned.

        Returns True of changes were made, False otherwise
        """

        # The whole point of the exercize is to determine _net_type. If it's already set, we shouldn't do anything 
        if self._net_type is not None:
            return False
        splinters = []
        assert self.get_source().is_specialized(), "Can't propagate types of source is not specialized."
        source = self.get_source()
        # 1. Sort all sinks into sets based on their input type (handle untyped ports later)
        source_net_type = source.get_net_type() if source is not None else None
        sinks_by_type = {}
        scope = self.get_parent_module()
        # Insert adaptor
        assert scope is not None
        assert is_module(scope)

        for sink in self.get_sinks() + self.get_wires():
            if not sink.is_specialized():
                continue
            sink_type = sink.get_net_type()
            if sink_type is self.get_net_type():
                continue
            if sink_type not in sinks_by_type:
                sinks_by_type[sink_type] = set()
            sinks_by_type[sink_type].add(sink)
        # 2. Determine net-type if we can
        if source_net_type is not None:
            net_type = source_net_type
        elif len(sinks_by_type) > 0:
            net_type = sinks_by_type.keys()[0].get_compatible_type(sinks_by_type.keys())
            assert net_type is not None
            if source is not None:
                self.set_net_type(net_type)
            else:
                from .constant import ConstantModule, Constant
                from .module import create_submodule
                source = create_submodule(ConstantModule, Constant(net_type, None))
                self.set_source(source)
        else:
            return False # Couldn't determine net_type at this point

        # 3. Create adapters for each type group, if possible; move corresponding sinks into new net
        for new_type, sinks in sinks_by_type.items():
            from .module import create_submodule
            # Even though implicit_adapt is not guaranteed to create a Module, in this case it is:
            # The whole point of calling it is to split the net, so we *need* it to make a submodule
            # We will assert that after the fact just to be certain.
            new_source = create_submodule(scope, implicit_adapt, source, new_type)
            assert new_source is not source
            assert new_source.get_net_type() is new_type
            new_net = Net(scope)
            new_net.set_source(new_source)
            for sink in sinks:
                self.move_sink(sink, new_net)
            if source.get_parent_module()._impl.has_explicit_name:
                naming_wire = Wire(new_type, parent_module=self.get_parent_module())
                naming_wire.local_name = source.interface_name # This creates duplicate names of course, but that will be resolved later on
                new_net.add_sink(naming_wire)
            splinters.append(new_net)
        # 4. Go through remaining sinks again. These should be original 'untyped' sinks, or sinks form the inserted
        #    adaptor instances. Either way, they should either already have the right type, or should have no type at all.
        changes = len(splinters) > 0
        for sink in self.get_sinks() + self.get_wires():
            if not sink.is_specialized():
                sink.set_net_type(source_net_type)
                changes = True
                continue
            sink_type = sink.get_net_type()
            if sink_type is not self.get_net_type():
                raise AssertionError(f"Adaptor {sink.get_parent_module()} has incorrect input type: {sink_type}. Type should be {self.get_net_type()}.")

        def resolve_composites(net: Net):
            if net.get_net_type().is_composite():
                source = net.get_source()
                _, (sub_sources, reverses) = source.get_all_member_junctions_with_names(add_self=False)
                for sink in net.get_sinks():
                    for sub_source, sub_sink, reversed in zip(sub_sources, sink.get_all_member_junctions(add_self=False), reverses):
                        if reversed:
                            sub_source.set_source(sub_sink, scope)
                        else:
                            sub_sink.set_source(sub_source, scope)

        # 5. Deal with composites: now that our net type is properly set, we'll have to create sub-nets for all the composite wires too
        resolve_composites(self)
        for splinter in splinters:
            resolve_composites(splinter)

        # 6. Cache the net types for all the splinters
        for splinter in splinters:
            splinter._net_type = splinter.get_source.get_net_type()
        # 7. Cache our own net type as well
        self._net_type = self.get_source.get_net_type()
        return changes

    def get_names(self) -> Sequence[str]:
        return tuple(j.get_diagnostic_name() for j in self.lhs_junctions.union(self.rhs_junctions))

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

    @abstractmethod
    def get_underlying_junction(self) -> 'Junction':
        raise NotImplementedError()

class EdgeType(Enum):
    NoEdge = 0
    Positive = 1
    Negative = 2
    Undefined = 3

class Junction(JunctionBase):
    def __init__(self, net_type: Optional[NetTypeMeta] = None, parent_module: 'Module' = None, *, keyword_only: bool = False):
        # !!!!! SUPER IMPORTANT !!!!!
        # In most cases, Ports of a Module are set on the cls level, not inside __init__() (or construct()).
        # There is a generic 'deepcopy' call in _init_phase2 that creates the instance-level copies for all the ports.
        # This means that __init__ for those ports is not getting called, the instance-level port is not a brand new
        # object, it's a copy of an already live one. This means, that none of this code gets executed for instance-level
        # ports. Right now, the most important thing here is that 'Context.register' doesn't get executed, but every time
        # we put stuff in here, that needs to be checked against the copy functionality in '_init_phase2' of 'Module.
        super().__init__()
        Context.register(self._context_change)
        assert parent_module is None or is_module(parent_module)
        from .module import Module
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
        self._source_net: Optional[Net] = None
        self._sink_net: Optional[Net] = None
        if net_type is not None:
            if not is_net_type(net_type):
                raise SyntaxErrorException(f"Net type for a port must be a subclass of NetType.")
            self.set_net_type(net_type)

    def set_source_net(self, net: Net) -> None:
        assert self._source_net is (None, net)
        self._source_net = net
    
    def get_source_net(self) -> Optional[Net]:
        return self._source_net

    def set_sink_net(self, net: Net) -> None:
        assert self._sink_net is (None, net)
        self._sink_net = net
    
    def get_sink_net(self) -> Optional[Net]:
        return self._sink_net

    def __str__(self) -> str:
        ret_val = self.get_diagnostic_name()
        if not self.is_specialized():
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

    def set_parent_module(self, parent_module: 'Module') -> None:
        assert parent_module is None or is_module(parent_module)
        assert self._parent_module is None or self._parent_module is parent_module
        assert self._parent_junction is None or self._parent_junction._parent_module is parent_module
        self._parent_module = parent_module
        # Recurse into members
        for member_junction, _ in self.get_member_junctions().values():
            member_junction.set_parent_module(parent_module)

    def get_parent_module(self) -> Optional['Module']:
        return self._parent_module

    def finalize_slices(self) -> None:
        if len(self.raw_input_map) > 0:
            assert not self.is_composite() # We can only generate slices of non-compound types (TODO: what about vectors???)
            self.concatenator = self.get_net_type().create_member_setter()
            self.set_source(None, self.get_parent_module())
            self.set_source(self.concatenator.output_port, self.get_parent_module())
            for (key, real_junction) in self.raw_input_map:
                self.concatenator.add_input(key, real_junction)
            self.raw_input_map = [] # Prevent re-creation of Concatenator
            # If the concatenator was created outside the normal body context (during type determination)
            # We'll have to make sure it's properly registered
            if Context.current() is None:
                assert False, "I DONT THINK THIS SHOULD HAPPEN!!!!!"
                self.concatenator.freeze_interface()
                self.concatenator._body()

    def set_net_type(self, net_type: Optional[NetType]) -> None:
        """
        Sets the net_type of the junction.

        Depending on the current net-type of the Junction, the following operations are permitted:

        - If the port is not specialized, net_type can be None or any valid NetType.
        - If the port is specialized, net_type is only allowed to be the exact same type as the current one.
          In that case, the operation is a no-op.
        """
        # Only allow the net_type to be set if it's not set yet
        # TODO: For now we also allow the net_type to be set from one abstract type to another one, but that can probably be tightened later
        #       For example, we could say that the new prot type must be an instance of the old port type...
        if self._net_type is net_type:
            return
        assert not self.is_specialized()
        assert net_type is not None, "TODO: I don't know why we would try to set a net_type to None, once it's already set."
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

            junction_type = inspect.getmro(type(self))[1]
            assert issubclass(junction_type, Junction)
            self.__class__ = create_junction_type(junction_type, net_type, extra_bases, extra_dict)
            net_type.setup_junction(self)

    def get_net_type(self) -> Optional[NetType]:
        return self._net_type
    def is_specialized(self) -> bool:
        return self._net_type is not None

    def set_source(self, source: Any, scope: 'Module') -> None:
        """
        Sets the source of the junction.
        This is a bit of a misnomer: the source might not be the 'true' source of the junction. It could be another
        sink, that's driven - eventually - by a source, which will become the true source.

        A typical example would be when an output port is assigned to another signal within a module. In that case,
        the output is not really the source of the assigned signal, whatever drives the output is.

        There are cases where both 'self' and 'source' are already part of nets, in which case those
        nets are merged. It's possible that during such merging, two true sources are identified, in which
        case an error is raised.

        If called with 'source' being None, the junction is removed from it's source_net, if any.

        Finally, source can be anything really that can be converted to a junction.
        """

        assert scope is not None
        assert is_module(scope)

        # Make sure we are in a scope where we can be assigned to
        if scope is self.get_parent_module():
            if is_input_port(self):
                raise SyntaxErrorException(f"Can't assign to {self.junction_kind} port '{self.get_diagnostic_name()}' from inside the module")
        else:
            if not is_input_port(self):
                raise SyntaxErrorException(f"Can't assign to {self.junction_kind} port '{self.get_diagnostic_name()}' from outside the module")

        # Handle the case, when we remove ourself from a net
        my_net: Net = self.get_source_net()
        if source is None:
            # We're removing the junction from it's net
            if my_net is not None:
                my_net.remove_sink(self)
            return

        # Convert source to a junction (if possible)
        # TODO: Not sure why I would want to convert all manners of exceptions into SyntaxErrors...
        #try:
        if True:
            source = convert_to_junction(source, type_hint=None)
            if source is None:
                # We couldn't create a port out of the value:
                raise SyntaxErrorException(f"Couldn't convert '{source}' to Junction.")
        #except Exception as ex:
        #    raise SyntaxErrorException(f"Couldn't bind port to value '{source}' with exception '{ex}'")
        assert is_junction_base(source)
        source = source.get_underlying_junction()
        assert is_junction(source)
        if self is source:
            # Assigning to ourselves is strange, but harmless
            return

        assert self.get_parent_module() is not None, "Can't bind free-standing junction"
        assert source.get_parent_module() is not None, "Can't bind to free-standing junction"
        if not self.allow_bind():
            raise SyntaxErrorException(f"Can't bind to port {self}: Port doesn't allow binding")

        # Determine if the 'source' is a true one or just another sink.
        # There are 5 cases:
        #   1. A wire. In that case we know that that's the source.
        #   2. An output of a sub-module: it is the source
        #   3. An input of the enclosing module: it is the source
        #   4. An input of a sub-module: it is *not* the source.
        #   5. An output of the enclosing module: same as (3). We *know* its not the source.

        if is_wire(source):
            is_true_source = True
        elif is_output_port(source) and source.get_parent_module() is not scope:
            assert source.get_parent_module()._impl.get_parent_module() is scope
            is_true_source = True
        elif is_input_port(source) and source.get_parent_module() is scope:
            is_true_source = True
        elif is_input_port(source) and source.get_parent_module() is not scope:
            assert source.get_parent_module()._impl.get_parent_module() is scope
            is_true_source = False
        elif is_output_port(source) and source.get_parent_module() is scope:
            is_true_source = False
        else:
            assert False

        # Create/update/merge the nets as needed
        source_net: Net = source.get_sink_net() if is_true_source else source.get_source_net()
        if my_net is None and source_net is None:
            net = Net(scope)
            net.add_sink(self)
            if is_true_source:
                net.set_source(source)
            else:
                net.add_sink(source)
        elif my_net is not None and source_net is None:
            if is_true_source:
                if my_net.get_source() is not None:
                    raise SyntaxErrorException(f"Can't add a second source {source} to {net}")
                my_net.set_source(source)
            else:
                net.add_sink(source)
        elif my_net is None and source_net is not None:
            source_net.add_sink(self)
        else:
            my_net.merge(source_net)

        # TODO: deal with this through inheritance instead of type-check!
        if is_output_port(source) and is_true_source:
            parent_module = source.get_parent_module()
            if parent_module is not None:
                parent_parent_module = parent_module._impl.get_parent_module()
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


    def __getitem__(self, key: Any) -> Any:
        if Context.current() == Context.simulation:
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
        self._junctions_before_scope = get_caller_local_junctions(frame_cnt=3)
        return self._scoped_port


    def __exit__(self, exception_type, exception_value, traceback):
        assert self._in_with_block
        self._in_with_block = False
        self._allow_auto_bind = False
        junctions_after_scope = get_caller_local_junctions(frame_cnt=3, filter=self._scoped_port)
        # We try to restore the old port under the following situations:
        #
        #     clk = some_clk
        #     with myclk as clk:
        #         y <<= clk     <-- here we should bind y to myclk
        #     x <<= clk         <-- here we should bind x to some_clk
        #
        # We might have multiple hits in 'locals' of the enclosing scope, in the following case:
        #
        #     with myclk as clk:
        #         some_other_clk = clk
        #     x <<= some_other_clk     <-- here we should bind x to myclk
        #     y <<= clk                <-- this should not work
        #
        # In this case, we want to disable 'clk', but keep 'some_other_clk' bindable, though I'm not sure it's possible to do.
        # The problem is that 'some_other_clk' is just a reference to clk, it's not it's own object, that can be re-bound and locals
        # in the enclosing scope is read-only. So, for now we're disallowing it. This should also be invalid:
        #
        #     some_other_clk = another_clk
        #     z <<= some_other_clk     <-- should bind z to another_clk 
        #     with myclk as clk:
        #         some_other_clk = clk
        #     x <<= some_other_clk     <-- here we should bind x to myclk
        #     y <<= clk                <-- this should not work
        #
        # The common theme is that the scoped port should appear only once in the enclosed scopes locals. If it was there upon __enter__,
        # we can restore it, if it wasn't, we can disallow it. Multiple hits are problematic
        if len(junctions_after_scope) > 1:
            raise SyntaxErrorException(f"This is not supported: scoped port {self} got assigned to multiple some local net references. Can't restore original state.")
        for name, junction in junctions_after_scope.items():
            assert junction is self._scoped_port
            old_junction = self._junctions_before_scope.get(name, None)
            self._scoped_port._update_real_port(old_junction)
        # Clean up the namespace: we need this so that the tracer doesn't try to insert a bunch of bogus wires into the generated RTL
        junction = None
        del junctions_after_scope
        del self._junctions_before_scope

    @abstractmethod
    @property
    def junction_kind(self) -> str:
        raise NotImplementedError

    @abstractmethod
    @classmethod
    def generate_junction_ref(cls, back_end: 'BackEnd') -> str:
        raise NotImplementedError

    @abstractmethod
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
        module_name = self.get_parent_module()._impl.get_diagnostic_name(False)
        if self.interface_name is None:
            name = "<unknown>"
        else:
            name = self.interface_name
        name = module_name + FQN_DELIMITER + name
        if add_location:
            name += self.get_parent_module()._impl.get_diagnostic_location(" at ")
        return name

    @staticmethod
    def _safe_call_by_name(obj, name, *kargs, **kwargs):
        if obj is None:
            return None
        return getattr(type(obj), name)(obj, *kargs, **kwargs)

    def _binary_op(self, other: Any, gate: 'Module', name: str) -> Any:
        context = Context.current()
        if context == Context.simulation:
            my_val = self.sim_value
            return Port._safe_call_by_name(my_val, name, other)
        elif context == Context.elaboration:
            return gate(self, other)
        else:
            sup = super()
            return getattr(sup, name)(other)

    def _rbinary_op(self, other: Any, gate: 'Module', name: str) -> Any:
        context = Context.current()
        if context == Context.simulation:
            my_val = self.sim_value
            return Port._safe_call_by_name(my_val, name, other)
        elif context == Context.elaboration:
            return gate(other, self)
        else:
            sup = super()
            return getattr(sup, name)(other)

    def _unary_op(self, gate: 'Module', name: str) -> Any:
        context = Context.current()
        if context == Context.simulation:
            my_val = self.sim_value
            return Port._safe_call_by_name(my_val, name)
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
            return Port._safe_call_by_name(my_val, name, other)
        elif context == Context.elaboration:
            return gate(self, other)
        else:
            sup = super()
            return getattr(sup, name)(other)

    def _rninput_op(self, other, gate: 'Module', name: str) -> Any:
        context = Context.current()
        if context == Context.simulation:
            my_val = self.sim_value
            return Port._safe_call_by_name(my_val, name, other)
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


    def __ilshift__elab(self, other: Any) -> 'Junction':
        from .module import Module
        scope = Module._parent_modules.top()
        # We allow the following:
        #
        #    a <<= b
        #    a <<= c
        #
        # This will blow up later, as both b and c are sources for a Net, but we can't be certain about it just here.
        # That is because, this is fine:
        #
        #   b <<= a
        #   a <<= c
        #
        # In both instances 'a' has a Net and since it's not organized, we don't know if a is a source or a sink in it.
        self.set_source(other, scope)
        return self

    def __ilshift__sim(self, other: Any) -> 'Junction':
        if self.is_composite():
            if other is None:
                for self_member in self.get_all_member_junctions(add_self=False):
                    self_member._set_sim_val(None)
            elif is_junction_base(other):
                # If something is connected to an otherwise unconnected port, we should support that.
                if other.source is None:
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

    def __ilshift__none(self, other: Any) -> 'Junction':
        return super().__ilshift__(other)

    def __ilshift__impl(self, other: Any) -> 'Junction':
        return self.__ilshift__none(other)

    def __ilshift__(self, other: Any) -> 'Junction':
        return self.__ilshift__impl(other)

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

    def __hash__(self):
        return id(self)

    def _context_change(self, context: Context) -> None:
        if context is None:
            self.__ilshift__impl = self.__ilshift__none
        elif context == Context.simulation:
            self.__ilshift__impl = self.__ilshift__sim
        elif context == Context.elaboration:
            self.__ilshift__impl = self.__ilshift__elab
        else:
            assert False

    def active_context(self) -> str:
        return self._context

    def set_interface_name(self, name: str) -> None:
        self.interface_name = name
        for member_name, (member_junction, _) in self.get_member_junctions().items():
            member_junction.set_interface_name(f"{self.interface_name}{MEMBER_DELIMITER}{member_name}")


    ############################################
    # abstractmethodCompund type support
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
        if self.interface_name is not None:
            member.set_interface_name(f"{self.interface_name}{MEMBER_DELIMITER}{name}")
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

    def is_deleted(self, netlist: 'Netlist') -> bool:
        """
        Returns True if the port (an optional auto-input with no driver) got deleted from the interface
        """
        return False







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

    def is_optional(self) -> bool:
        return False




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
        from .module import Module
        if parent_module is None:
            if not Module._parent_modules.is_empty():
                parent_module = Module._parent_modules.top()
        super().__init__(net_type, parent_module)
        if parent_module is not None:
            parent_module._impl.register_wire(self)
        self.rhs_expression: Optional[Tuple[str, int]] = None # Filled-in by the parent_module during the 'generation' phase to contain the expression for the right-hand-side value, if inline expressions are supported for this port.
        self.local_name: Optional[str] = None

    @classmethod
    def is_instantiable(cls) -> bool:
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

