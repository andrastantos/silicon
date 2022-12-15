"""
This module contains utility modules, classes and functions to implement member and slice access to various net_types.

It handles recursive member accesses, such as:

out_a[5:1][0] = in_a

or

out_a.a.b[3:1][2] = in_a.b.c

etc.
"""
from typing import Tuple, Sequence, Any, Generator

from .module import GenericModule, Module, InlineBlock
from .port import Junction, Input, Output, Port
from .net_type import KeyKind
from .exceptions import SimulationException, SyntaxErrorException, InvalidPortError
from .netlist import Netlist
from .utils import Context

"""
There should be a generic (non type-specific) way of handling slicing, or even more generally accessing members.
The reason for the generic support is this: when one writes down expressions such as:

    a <<= b[3:0]
    c[3] <<= d
    e[3:2][0] <<= a[1:0][1]

the system doesn't necessarily know the types of any of the objects involved. So, all we can do is duly note all
the accesses, and resolve them only once the types are known.

## RHS expressions

When one writes `a[3:0]` or `a[3]` in a RHS context, what we mean is this:

    intermediate_wire <<= Slice(Range(3,0))(a)
    intermediate_wire <<= Slice(3)(a)

No types are needed to be known here, we can resolve them later. `Slice`s `body` will only be called, once the
type of `a` is known, so we can do all the type-specific lookup inside.

This works even for cascaded accessors:

    a[3:0][2:1][0]

will turn into:

    intermediate_wire <<= Slice(0)(Slice(Range(2:1)(Slice(Range(3:0)(a)))))

Type changes along the way are also tolerated.

For Composites, member access happens through `__getattr__` instead of `__getitem__`, but the logic is the same.

This is the easy stuff. The complexity comes with LHS expressions.

## LHS expressions

When we assign to a slice of a wire `a[3:0]` or `a[3]`, what we really mean is a portion of a `Concatenate` instance.
Or, if we really wanted to, simply a special Module of our choosing. Let's call it `PhiSlice`.

This is the only place, really, so far, where the data-flow has a convergence point, sort of a PHI-node,
we'll need to create and insert. Thus the name 'Phi'...

So, when we see this code:

    a[3:0] <<= b
    a[4] <<= c
    a[7:5] <<= d

what we want to get out of it is:

    a <<= PhiSlice(Range(3,0),4,Range(7:5))(b,c,d)

Again, types are not interesting, those will get resolved later. The *collection* of all the assignments and the
maintenance of the ranges however *is* the job at hand.

What's more, due to the behavior of <<=, we will see a `__getitem__` call on `a`, followed by `__ilshift__` on
*whatever that returns*. Same here:

    a[3:0][2] <<= b

Things get even more complicated with this:

    a[3:0] = b
    a[7:4][3] = c

Here we start seeing `__setitem__` calls for the last slice, instead an `__ilshift__` after the last slice.
It can be supported, but maybe we should start by asserting in those...

## Combining the two.

Notice how both LHS and RHS contexts involve `__getitem__`. So, whatever that returns, it has to be a two-face entity.
It should work as a `JunctionBase` object in the sense that it should have `__getitem__` (and `__getattr__`) 
on it to support further sub-slicing as well as `__ilshift__` to support assignment.

It is not a `JunctionBase` however in the sense that *its* `__ilshift__` should start collecting the info for the
future creation of `PhiSlice`.

`__getitem__` on `Junction` and this two-face entity also can't simply instantiate the `Slice` instance, because
we don't yet know if we're on the LHS or the RHS. That instantiation will need to be delayed to the
`convert_to_junction` logic.

Let's call this magical object `UniSlicer`
"""

from .port import JunctionBase, IgnoreMeAfterIlShift
from .utils import first, get_common_net_type
from typing import Optional

class UniSlicer(JunctionBase):
    def __init__(self, parent: JunctionBase, key: Any, key_kind: KeyKind, parent_module: Optional['Module']):
        super().__init__(parent_module)
        with self._member_guard:
            self.parent = parent
            self.key = key
            self.key_kind = key_kind
            self._slice = None
    
    def convert_to_junction(self, type_hint: Optional['NetType']=None) -> Optional[Junction]:
        # If this is called, we're in a RHS context, that is, we're binding to another port as its source.
        # We can create a Slice object with the proper key even without knowing the net-types of anything.
        # We will deal with types - and the validity of the key - in the body of Slice.
        #
        # the __call__ might end up calling convert_to_junction recursively, if parent is also a UniSlicer
        #
        # To avoid several instances being generated, we cache our conversion and return that.
        # This is important for locals assigned with the '=' operator. See test_basics.py:test_reg3b for an example.
        if self._slice is None:
            self._slice = Slice(self.key, self.key_kind)(self.parent)
        return self._slice

    def ilshift__elab(self, other: Any) -> 'type':
        # If this is called, we're in a LHS context, that is: we are used to assign to a slice of a net.
        # What we need to do now is to dump all the slice info into our parent so that the PhiSlice
        # module can later be created.
        scope = Netlist.get_current_scope()
        self.set_partial_source(tuple(), other, scope)
        return IgnoreMeAfterIlShift

    def __getattr__(self, name: str) -> Any:
        # If this is called, we're asked for a member, such as:
        #     a[3].pink <<= blue 
        #     blue <<= a[0].yellow
        # We don't know if we're in a LHS or RHS context.
        # It of course is also possible that it's simply an error in code:
        #     something = a[0].kreffufle
        if Context.current() == Context.simulation:
            raise SimulationException("FIXME: member access during simulation is not yet supported")
        else:
            return UniSlicer(self, name, KeyKind.Member, self.get_parent_module())
    
    def set_partial_source(self, key_chain: Sequence[Tuple[Any, KeyKind]], source: Any, scope: 'Module') -> None:
        key_chain = ((self.key, self.key_kind), ) + key_chain
        self.parent.set_partial_source(key_chain, source, scope)

    def get_default_name(self, scope: object) -> str:
        return "uni_slicer"
class Slice(GenericModule):
    input_port = Input()
    output_port = Output()

    def construct(self, key: Any, key_kind: KeyKind) -> None:
        self.key = key
        self.key_kind = key_kind

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        return self.implementation.get_inline_block(back_end, target_namespace)

    def body(self) -> None:
        self.implementation = self.input_port.get_rhs_slicer(self.key, self.key_kind)
        self.output_port <<= self.implementation(self.input_port)

class PhiSlice(GenericModule):
    output_port = Output()

    def construct(self, key_chains: Sequence[Sequence[Tuple[Any, KeyKind]]]) -> None:
        # This is a complicated argument type, so let's unpack it:
        # We need to gather all the partial assignments to a Net and generate a concatenated expression for it.
        # (Side-note: for interfaces, this is even more complicated, as we need to deal with 'reversed' members)
        # We need to have a list for all the constituents.
        # How to deal with recursion though? What happens in this case:
        #   a[3:0][3] <<= b
        #   a[3:0][2:0][1] <<= c
        # Even more importantly, what happens in this case:
        #   my_if.my_array[3:0][0].something.a_number[4:0] <<= milk
        # We don't know the types involved necessarily, so all we can do is to store the whole chain of keys and
        # punt the resolution later. Thus, each key is actually a chain of keys.
        self.key_chains = key_chains

    def create_positional_port_callback(self, idx: int, net_type: Optional['NetType'] = None) -> Tuple[str, Port]:
        # Create the associated input to the key. We don't support named ports, only positional ones.
        if idx >= len(self.key_chains):
            raise InvalidPortError()
        name = f"slice_{idx}"
        ret_val = Input(net_type)
        return (name, ret_val)

    def create_named_port_callback(self, name: str, net_type: Optional['NetType'] = None) -> Optional[Port]:
        raise InvalidPortError()

    def body(self) -> None:
        common_net_type = get_common_net_type(self.get_inputs().values())
        if common_net_type is None:
            raise SyntaxErrorException(f"Can't figure out output port type for PhiSlice {self}")
        self.implementation = common_net_type.get_lhs_slicer(self.key_chains)
        self.output_port <<= self.implementation(*self.get_inputs().values())

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
        return self.implementation.get_inline_block(back_end, target_namespace)

