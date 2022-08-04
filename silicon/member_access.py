"""
This module contains utility modules, classes and functions to implement member and slice access to various net_types.

It handles recursive member accesses, such as:

out_a[5:1][0] = in_a

or

out_a.a.b[3:1][2] = in_a.b.c

etc.
"""
from typing import Tuple, Sequence, Any, Generator

from .module import GenericModule, Module, InlineBlock, InlineExpression
from .port import Junction, Input, Output, Port, ScopedPort
from .net_type import KeyKind
from .tracer import no_trace
from .utils import BoolMarker, get_caller_local_junctions
from .exceptions import SyntaxErrorException

class MemberGetter(object):
    @staticmethod
    def resolve_key_sequence_for_get(keys: Sequence[Tuple[Any, KeyKind]], for_junction: Junction) -> Junction:
        # Implements junction[3:2][2:1] or junction[3:2][0] type recursive slicing
        # Returns the junction that resolves to they final key.
        # For numbers and slices, this is easy, because slicing doesn't change the
        # underlying net_type. However for things, like interfaces and structs, each
        # member-access can change the port type and might need the generation of
        # accessors (it appears that structs and interfaces require you to do
        # member-level assignment anyway, so generating accessors for all but
        # bottom-most members is probably the right abstraction.)
        # NOTE: This system will break down if there ever was a construct that
        #       has members of different types, yet only allow assignment as a whole
        #       in any of the supported back-ends.
        # Each key is actually a tuple, where the first member is a slice or a member name
        # and the second which is set to 'Index' for slice-type accesses ([] operator)
        # and 'Member' to member-style accesses (. operator)
        #
        # This routine takes advantage of the net_type-level resolve_key_sequence_for_get method, which
        # works a little differently: it resolves *as much* of the key-chain as it can and
        # returns the final junction and the remaining sequence as the return value.
        remaining_keys = keys
        next_junction = for_junction
        while remaining_keys is not None:
            remaining_keys, next_junction = next_junction.get_net_type().resolve_key_sequence_for_get(remaining_keys, next_junction)
        return next_junction

    class GetSlice(GenericModule):
        output_port = Output()
        input_port = Input()

        def construct(self, keys: Sequence[Tuple[Any, KeyKind]]) -> None:
            self._keys = keys


        def body(self) -> None:
            if not self.input_port.is_specialized():
                raise SyntaxErrorException(f"Input port type is not specified for slice {self}")
            if not hasattr(self.input_port.get_net_type(), "get_slice"):
                raise SyntaxErrorException(f"Net type {self.input_port.get_net_type()} doesn't support slice operations")

            net_type = self.input_port.get_net_type()
            final_key, final_junction = net_type.resolve_key_sequence_for_get(self._keys, self.input_port)
            assert final_key is None, f"We should recurse into subtypes here!!!!"
            self.output_port <<= final_junction
            # This is very important! In get_inline_block we will get the source of output_port to get to the true implementation.
            # If we didn't delete the local variable, *it* would become the source and get_inline_block would spiral into an
            # infinite loop.
            del(final_junction)

        def get_inline_block(self, back_end: 'BackEnd', target_namespace: Module) -> Generator[InlineBlock, None, None]:
            # Trampoline to the inner implementation for inlining. The only difference is that we'll have to update the referenced port.
            implementor = self.output_port.get_source_net().get_source().get_parent_module()
            for ret_val in implementor.get_inline_block(back_end, target_namespace):
                assert len(ret_val.target_ports) == 1
                ret_val.set_target_ports((self.output_port, )) # Override target port
                yield ret_val

        def is_combinational(self) -> bool:
            """
            Returns True if the module is purely combinational, False otherwise
            """
            return False

        # This module contains an Accessor module, which does the actual implementation.
        # As such, the default simulation framework should just work fine
        #def simulate(self) -> TSimEvent:
        #    return super().simulate()



    def __init__(self, parent_junction: 'Junction', keys: Sequence[Tuple[Any, bool]]):
        self._keys = list(keys)
        self._parent_junction = parent_junction
        self._slice_port = None
        self._in_with_block = False
        self._in_allow_auto_bind = BoolMarker()
        self._allow_auto_bind = True
        self._scoped_port = None
        self._junctions_before_scope = None

        self._initialized = True

    def get_parent_junction(self) -> 'Junction':
        return self._parent_junction

    def get_underlying_junction(self) -> 'Junction':
        if self._slice_port is None:
            # We'll create the accessor module, even though it doesn't yet know its innards or if it can have innards at all.
            # That can only happen later, once the net_type of self._parent_junction is known, that is when GetSlice.body()
            # gets called. Still, we have now an output port that can be used within the netlist.
            self._slice_port = MemberGetter.GetSlice(keys=self._keys)(self._parent_junction)
        return self._slice_port.get_underlying_junction()

    def __ilshift__(self, other: Any) -> 'Junction':
        if not self._parent_junction.is_specialized():
            raise SyntaxErrorException("Can only bind to a slice of a specialized port (one with a type).")
        net_type = self._parent_junction.get_net_type()
        if not hasattr(net_type, "set_member_access"):
            raise TypeError()
        keys = self._keys
        net_type.set_member_access(keys, other, self._parent_junction)
        return self

    def allow_auto_bind(self) -> bool:
        """
        Determines if auto-port binding to this port is allowed.
        Defaults to True, but for scoped ports, get set to False
        upon __exit__
        """
        # We have to short-circuit the case where the _slice_port has not been created yet: that results in an infinite loop
        # because the constructor calls back allow_auto_bind...
        #if self._in_allow_auto_bind:
        #    return False
        #with self._in_allow_auto_bind:
        #    return self.get_underlying_junction().allow_auto_bind()
        return self._allow_auto_bind

    def allow_bind(self) -> bool:
        """
        Determines if port binding to this port is allowed.
        Defaults to True, but for scoped ports, get set to
        False to disallow shananingans, like this:
            with my_port as x:
                x <<= 3
        """
        return self.get_underlying_junction().allow_bind()


    def __add__(self, other: Any) -> Any:
        return self.get_underlying_junction().__add__(other)

    def __sub__(self, other: Any) -> Any:
        return self.get_underlying_junction().__sub__(other)

    def __mul__(self, other: Any) -> Any:
        return self.get_underlying_junction().__mul__(other)

    def __floordiv__(self, other: Any) -> Any:
        return self.get_underlying_junction().__floordiv__(other)

    def __mod__(self, other: Any) -> Any:
        return self.get_underlying_junction().__mod__(other)

    def __divmod__(self, other: Any) -> Any:
        return self.get_underlying_junction().__divmod__(other)

    def __pow__(self, other: Any, modulo = None) -> Any:
        return self.get_underlying_junction().__pow__(other)

    def __lshift__(self, other: Any) -> Any:
        return self.get_underlying_junction().__lshift__(other)

    def __rshift__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rshift__(other)

    def __and__(self, other: Any) -> Any:
        return self.get_underlying_junction().__and__(other)

    def __xor__(self, other: Any) -> Any:
        return self.get_underlying_junction().__xor__(other)

    def __or__(self, other: Any) -> Any:
        return self.get_underlying_junction().__or__(other)

    def __truediv__(self, other: Any) -> Any:
        return self.get_underlying_junction().__truediv__(other)


    def __radd__(self, other: Any) -> Any:
        return self.get_underlying_junction().__radd__(other)

    def __rsub__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rsub__(other)

    def __rmul__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rmul__(other)

    def __rtruediv__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rtruediv__(other)

    def __rfloordiv__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rfloordiv__(other)

    def __rmod__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rmod__(other)

    def __rdivmod__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rdivmod__(other)

    def __rpow__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rpow__(other)

    def __rlshift__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rlshift__(other)

    def __rrshift__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rrshift__(other)

    def __rand__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rand__(other)

    def __rxor__(self, other: Any) -> Any:
        return self.get_underlying_junction().__rxor__(other)

    def __ror__(self, other: Any) -> Any:
        return self.get_underlying_junction().__ror__(other)


    def __neg__(self) -> Any:
        return self.get_underlying_junction().__neg__()

    def __pos__(self) -> Any:
        return self.get_underlying_junction().__pos__()

    def __abs__(self) -> Any:
        return self.get_underlying_junction().__abs__()

    def __invert__(self) -> Any:
        return self.get_underlying_junction().__invert__()


    def __bool__(self) -> bool:
        return self.get_underlying_junction().__bool__()

    def __lt__(self, other: Any) -> bool:
        return self.get_underlying_junction().__lt__(other)

    def __le__(self, other: Any) -> bool:
        return self.get_underlying_junction().__le__(other)

    def __eq__(self, other: Any) -> bool:
        return self.get_underlying_junction().__eq__(other)

    def __ne__(self, other: Any) -> bool:
        return self.get_underlying_junction().__ne__(other)

    def __gt__(self, other: Any) -> bool:
        return self.get_underlying_junction().__gt__(other)

    def __ge__(self, other: Any) -> bool:
        return self.get_underlying_junction().__ge__(other)


    def __getitem__(self, key: Any) -> Any:
        # We get here in the following context:
        # out = in1[4:0][1]
        # self represents in1[4:0]. We would have to create a new MemberGetter with the new key that represnts the sub-slice.
        # NOTE: this can be recursive as in in1[100:0][50:0][25:0][3:0][2]
        return MemberGetter(self._parent_junction, self._keys + [(key, KeyKind.Index)])

    def __getattr__(self, name:str) -> Any:
        return MemberGetter(self._parent_junction, self._keys + [(name, KeyKind.Member)])

    def __setitem__(self, key: Any, value: Any) -> None:
        # We get here in the following context:
        # out[4:0][1] = 3
        # This is tricky. 'self' represents out[4:0] and now we'll have to somehow create the sub-slice of that.
        # We need to limit ourselves to the following:
        # 1. All member or slice accesses must be on typed ports. Now, they might be abstract ports, but should have at least a known type.
        # 2. have something similar to 'resolve_key_sequence' on a type that can resolve as much of the sequence as possible
        #    but instead of creating an accessor Module, would return *something* that can 'collects' assignments to the aggregate type.
        #
        # The old process was the following
        # 1. resolve_key_sequence returned the result key
        # 2. This key was used with set_slice on the *original* junction
        # 3. set_slice simply recorded the fact that a slice of this-or-that kind was accessed on the junction
        #    It however also made sure that the RHS expression was a junction, that is, it resolved any MemberGetters and/or constants
        # 4. Later in the process finalize_slices gets called (from _body) which creates the Concatenator Modules.
        #    This is the point, where a Concatenator could be created outside of the normal 'body' process, at least *I think*.
        #    For now, I've put an assert there so I'll catch if it happens.
        #
        # So, really the process should be:
        # 1. No need to call resolve_key_sequence right here. DONE
        # 1. set_slice should change to set_member_access or something. The functionality of it should more or less remain the same,
        #    except it should store the whole key sequence. DONE
        # 2. When finalize_slices gets called, it should generate a MemberSetter Module for the result type, again, more or less as before.
        #    Still no need to resolve any of the key sequences, just pass them on to the MemberSetter. DONE
        # 3. The MemberSetter is type-specific. For Numbers, it's what it was before (except that it resolves the key-sequences now)
        #    NOTE: this means that we can't set members on an untyped junction, but that's already checked down below. DONE
        # 4. For Number, MeberSetter generates a simple inline expression. DONE
        # 5. For Interfaces and what not, MemberSetter generates a set of field-expressions (element-wise assignment) NOT DONE
        # 6. We need machinery for MemberSetters to support composition for sub-key accesses.
        #    Maybe the way to communicate this is for get_inline_block to return a third 'field-expression' variety.
        #    This would give you a field-ID and an expression to assign to. To make it composable, it should give you either multiple
        #    entries or a list of expressions. NOT DONE
        # 6. For structs to be useful, we would need some sort of 'default assignment'. This could be lexical, that is 'last assignment wins'
        #    or another operator, such as **= or something. Maybe the lexical is better, but that involves making sure that multiple assignments
        #    to the same key are allowed (which is hard for Numbers and Vectors), and so probably assignment order will have to be maintained in
        #    whatever set_slice uses to store the keys. That way, later one, when the Concatenator is created (that is, when the full set of
        #    assignments are known) they can be reconciled. That is going to be one *fun* algorithm to write and debug though...
        #    NOTE: set_slice already stores things in a list, so it's order-preserving already. NOT DONE
        keys = self._keys + [(key, KeyKind.Index)]
        if value._parent_junction is self._parent_junction and value._keys == keys:
            return
        if not self._parent_junction.is_specialized():
            raise SyntaxErrorException("Can only set an item of a specialized port (one with a type).")
        net_type = self._parent_junction.get_net_type()
        if not hasattr(net_type, "set_member_access"):
            raise TypeError()
        net_type.set_member_access(keys, value, self._parent_junction)

    def __setattr__(self, name: str, value: Any) -> None:
        # We have to be tricky here! This thing gets invoked every time an attribute gets set, whether it exists or not.
        if name in dir(self) or name == "_initialized" or "_initialized" not in dir(self):
            super().__setattr__(name, value)
        else:
            if not self._parent_junction.is_specialized():
                raise SyntaxErrorException("Can only assign to a slice of a specialized port (one with a type).")
            net_type = self._parent_junction.get_net_type()
            if not hasattr(net_type, "resolve_key_sequence"):
                raise TypeError()
            keys = self._keys + [(name, KeyKind.Member)]
            final_key, final_junction = net_type.resolve_key_sequence(keys, self._parent_junction)
            final_type = final_junction.get_net_type()
            if not hasattr(final_type, "set_slice"):
                raise TypeError()
            final_type.set_slice(final_key, value, final_junction)



    def __delitem__(self, key: Any) -> None:
        # I'm not sure what this even means in this context
        raise TypeError()


    def __enter__(self) -> 'JunctionBase':
        assert not self._in_with_block
        self._in_with_block = True
        self._scoped_port = ScopedPort(self)
        self._junctions_before_scope = get_caller_local_junctions(3)
        self._allow_auto_bind = True
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
        self._junctions_before_scope = None

    @property
    def sim_value(self) -> Any:
        return self.parent_junction.sim_value


