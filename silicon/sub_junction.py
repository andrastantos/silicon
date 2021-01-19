from .port import Junction, JunctionBase, Input, Output, Wire

assert False, "I don't know what a sub-junction is!!!"

class SubJunction(Junction):
    
    def __init__(self, net_type: Optional[NetType] = None, parent_module: 'Module' = None, *, keyword_only: bool = False):
        assert False, "I don't know what a sub-junction is!!!"
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
        if self._parent_module is not None:
            self.set_context(self._parent_module._impl.active_context())
        else:
            self.set_context(None)
        self.set_net_type(net_type)

    
    def set_parent_module(self, parent_module: 'Module') -> None:
        assert parent_module is None or is_module(parent_module)
        assert self._parent_module is None or self._parent_module is parent_module
        self._parent_module = parent_module
        self.set_context(self._parent_module._impl.active_context())

    def get_parent_module(self) -> Optional['Module']:
        return self._parent_module

    
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
    def reverse_port(cls) -> Type:
        return Output
    @classmethod
    def is_instantiable(cls) -> bool:
        return True
    junction_kind: str = "input"
