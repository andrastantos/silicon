from typing import Any, Optional, Dict, Sequence, FrozenSet, Iterator, Callable, Union
from weakref import WeakKeyDictionary, WeakValueDictionary

from silicon.exceptions import SyntaxErrorException
from .ordered_set import OrderedSet
from collections.abc import MutableSet
from itertools import chain
#from weakref import WeakKeyDictionary, WeakValueDictionary, WeakSet

WeakKeyDictionary = dict
WeakValueDictionary = dict
WeakSet = OrderedSet

def _dump_obj(obj) -> str:
    from .utils import is_module, is_junction_base, is_junction, is_port, is_input_port, is_output_port, is_wire
    if is_module(obj): kind = "module "
    elif is_wire(obj): kind = "wire "
    elif is_output_port(obj): kind = "output "
    elif is_input_port(obj): kind = "input "
    elif is_port(obj): kind = "port "
    elif is_junction(obj): kind = "junction "
    elif is_junction_base(obj): kind = "junction_base "
    else: kind = ""
    if obj is None:
        return f"<{kind}None>"
    return f"<{kind}{id(obj):x}>"

class ScopeTable(object):
    """
    A symbol table for a single scope.
    
    Symbols are names for 'things'. The table contains symbols within a single scope.

    Initially, duplicate symbols are allowed, there is a method to disambiguate collisions.

    There are several kind of symbols allowed:
    - hard symbols are ones that have an explicitly user-defined name, and should never renamed automatically.
      If collisions exist between two hard symbols, that is an error.
    - soft symbols are ones that have a 'suggested' name, but could be renamed if needed to resolve conflicts.
      Conflicts between a hard and one or more soft-names are also allowed, in which case all the soft symbols
      are moved out of the way.
    - automatic symbols are ones that don't have a user defined name at all and will need a generated name.
      These rely on the referenced object to generate a default name, which - after conflict resolution -
      should become unique.

    ScopeTable uses weak references to the objects it contains: if an object gets
    deleted one way or another, we shouldn't hold on to it just for the sake of the symbol table. 
    """

    class Reserved(object):
        pass
    reserved = Reserved()
    def __init__(self):
        self.hard_symbols: WeakValueDictionary[str, object] = WeakValueDictionary()
        self.soft_symbols: Dict[str, WeakSet[object]] = {}
        self.auto_symbols: WeakSet[object] = WeakSet()
        self.named_auto_symbols: WeakSet[object] = WeakSet()
        self.hard_names: WeakKeyDictionary[object, MutableSet[str]] = WeakKeyDictionary()
        self.soft_names: WeakKeyDictionary[object, MutableSet[str]] = WeakKeyDictionary()

        from .back_end import get_reserved_names
        for name in get_reserved_names():
            self.hard_symbols[name] = ScopeTable.reserved

    def add_hard_symbol(self, obj: object, name: str) -> None:
        assert name is not None
        # Remove any auto-symbols: we don't want them around anymore, now that we have a proper name
        try:
            self.del_auto_symbol(obj)
        except KeyError:
            pass
        if name in self.hard_symbols and self.hard_symbols[name] is not obj:
            if self.hard_symbols[name] is ScopeTable.reserved:
                raise SyntaxErrorException(f"Name {name} is reserved and can't be used")
            else:
                raise SyntaxErrorException(f"Name {name} is already used and can't be duplicated")
        self.hard_symbols[name] = obj
        try:
            self.hard_names[obj].add(name)
        except KeyError:
            self.hard_names[obj] = set((name,))

    def add_soft_symbol(self, obj: object, name: str) -> None:
        assert name is not None
        # Remove any auto-symbols: we don't want them around anymore, now that we have a proper name
        try:
            self.del_auto_symbol(obj)
        except KeyError:
            pass
        try:
            self.soft_symbols[name].add(obj)
        except KeyError:
            self.soft_symbols[name] = WeakSet((obj,))
        try:
            self.soft_names[obj].add(name)
        except KeyError:
            self.soft_names[obj] = set((name,))

    def add_auto_symbol(self, obj: object) -> None:
        self.auto_symbols.add(obj)

    def del_hard_symbol(self, obj: object, name: str) -> None:
        assert self.hard_symbols[name] is obj
        del self.hard_symbols[name]
        self.hard_names[obj].remove(name)

    def del_soft_symbol(self, obj: object, name: str) -> None:
        assert obj in self.soft_symbols[name]
        self.soft_symbols[name].remove(obj)
        self.soft_names[obj].remove(name)

    def del_auto_symbol(self, obj: object) -> None:
        self.auto_symbols.remove(obj)

    def replace_symbol(self, old_obj: object, new_obj: object) -> None:
        # Replace all mentions of old with new
        if old_obj in self.hard_names:
            hard_name = self.hard_names[old_obj]
            self.del_hard_symbol(old_obj, hard_name)
            self.add_hard_symbol(new_obj, hard_name)
        if old_obj in self.soft_names:
            for soft_name in tuple(self.soft_names[old_obj]):
                self.del_soft_symbol(old_obj, soft_name)
                self.add_soft_symbol(new_obj, soft_name)
        if old_obj in self.auto_symbols:
            self.add_auto_symbol(new_obj)

    def is_reserved_name(self, name) -> bool:
        from .back_end import get_reserved_names
        return name in get_reserved_names()

    def get_objects(self, name: Optional[str]) -> FrozenSet[object]:
        if name is None:
            return frozenset(self.auto_symbols)

        try:
            hard_objects = (self.hard_symbols[name],)
        except KeyError:
            hard_objects = ()
        try:
            soft_objects = self.soft_symbols[name]
        except KeyError:
            soft_objects = ()
        return frozenset(chain(hard_objects, soft_objects))

    def exists(self, obj: object) -> bool:
        if obj in self.auto_symbols:
            return True
        if obj in self.named_auto_symbols:
            return True
        if obj in self.hard_names:
            return True
        if obj in self.soft_names:
            return True
        return False

    def get_names(self, obj: object) -> FrozenSet[str]:
        try:
            hard_names = self.hard_names[obj]
        except KeyError:
            hard_names = ()
        try:
            soft_names = self.soft_names[obj]
        except KeyError:
            soft_names = ()
        return frozenset(chain(hard_names, soft_names))

    def get_hard_names(self, obj: object) -> FrozenSet[str]:
        try:
            return frozenset(self.hard_names[obj])
        except KeyError:
            return ()

    def get_soft_names(self, obj: object) -> FrozenSet[str]:
        try:
            return frozenset(self.soft_names[obj])
        except KeyError:
            return ()

    def is_auto_symbol(self, obj: object) -> bool:
        if obj in self.auto_symbols:
            return True
        if obj in self.named_auto_symbols:
            return True
        if obj in self.hard_names:
            return False
        if obj in self.soft_names:
            return False
        assert False, "We don't know about this object. This question is not well formed."

    def make_unique(self, scope: object, delimiter: Union[str,Callable] = "_") -> None:
        """
        Rename soft- and auto-symbols as needed to make all symbols unique
        """
        delimiter_str = delimiter
        def default_delimiter(obj):
            return delimiter_str
        if isinstance(delimiter, str):
            delimiter = default_delimiter

        def name_exists(name: str) -> bool:
            if name in self.hard_symbols:
                return True
            if name in self.soft_symbols:
                return True
            return False

        # First let's deal with unnamed objects. These can create further name collisions that we'll resolve in the next loop
        for auto_obj in tuple(self.auto_symbols):
            auto_name = auto_obj.get_default_name(scope)
            self.add_soft_symbol(auto_obj, auto_name)
            self.named_auto_symbols.add(auto_obj)
        assert len(self.auto_symbols) == 0
        # We can now resolve all remaining name collisions
        for name, objects in tuple(self.soft_symbols.items()):
            have_hard_symbol = name in self.hard_symbols
            if len(objects) > 1 or have_hard_symbol:
                # We will leave the first object as-is, only rename subsequent ones. We also create a copy of 'objects'
                # because we modify it inside the loop
                rename_list = tuple(objects) if have_hard_symbol else tuple(objects)[1:]
                idx = 1
                for obj in rename_list:
                    unique_name = f"{name}{delimiter(obj)}{idx}"
                    # Need to be careful here: we try to rename 'my_thing' to 'my_thing_42', but of course it's possible
                    # that there's already an object named 'my_thing_42'.
                    while name_exists(unique_name):
                        idx += 1
                        unique_name = f"{name}{delimiter(obj)}{idx}"
                    self.del_soft_symbol(obj, name)
                    self.add_soft_symbol(obj, unique_name)
                assert len(objects) <= 1



class SymbolTable(object):
    """
    A global symbol table.
    
    Symbols are names for 'things'. The table contains symbols arranged into scopes.
    What scopes really are, is not really the business of the SymbolTable as long as they are hashable.

    Initially, duplicate symbols are allowed, there is a method to disambiguate collisions.

    There are several kind of symbols allowed:
    - hard symbols are ones that have an explicitly user-defined name, and should never renamed automatically.
      If collisions exist between two hard symbols, that is an error.
    - soft symbols are ones that have a 'suggested' name, but could be renamed if needed to resolve conflicts.
      Conflicts between a hard and one or more soft-names are also allowed, in which case all the soft symbols
      are moved out of the way.
    - automatic symbols are ones that don't have a user defined name at all and will need a generated name.
      These rely on the referenced object to generate a default name, which - after conflict resolution -
      should become unique.

    SymbolTable uses weak references to the objects it contains: if an object gets
    deleted one way or another, we shouldn't hold on to it just for the sake of the symbol table. 
    """

    def __init__(self):
        self.top = ScopeTable()
        self.scopes: WeakKeyDictionary[object, ScopeTable] = WeakKeyDictionary()

    def __getitem__(self, scope: object) -> ScopeTable:
        if scope is None:
            return self.top
        try:
            return self.scopes[scope]
        except KeyError:
            self.scopes[scope] = ScopeTable()
            return self.scopes[scope]
        
    def make_unique(self, delimiter: Union[str,Callable] = "_") -> None:
        for scope, table in self.scopes.items():
            table.make_unique(scope, delimiter)