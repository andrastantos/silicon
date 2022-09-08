# For later

- We can theoretically remove convert_to_junction from set_member_access, but it generates much worse RTL. The reason for it seems to be that we delay the creation of the Constant module to where the slices are resolved, and so it won't get inlined into the assignment expression for the concatenator. This can probably traced down and fixed, but I'll leave it as-is for now.

# Composite rework

- We should really really handle composites natively and have the proper combiner/splitter modules inserted, instead of this awful hack of member_junctions.

Here's where we should start: how does member-access (both LHS and RHS) for Number work?

There is generic functionality in 'member_access.py', then there's a set of methods on `Number` to support the specialization of this generic behavior.

The reason for the generic support is this: when one writes down an expression such as:

    a <<= b[3:0]
    c[3] <<= d
    e[3:2][0] <<= a[1:0][1]

the system doesn't necessarily know the types of any of the objects involved. So, all we can do is duly note all the accesses, and resolve them only once the types are known.

The key object in these machinations is `MemberGetter`.

Actually, things are not as they seem: MemberGetter is not as generic as one could imagine, and types are needed to be known.

So, maybe we should think of what it *should* be instead of what it is.

So, here's the thing:

## RHS expressions

When one writes `a[3:0]` or `a[3]` in a RHS context, what we mean is this:

    intermediate_wire <<= Slice(Range(3,0))(a)
    intermediate_wire <<= Slice(3)(a)

No types are needed to be known here, we can resolve them later. `Slice`s `body` will only be called, once the type of `a` is known, so we can do all the type-specific lookup inside.

This works even for cascaded accessors:

    a[3:0][2:1][0]

will turn into:

    intermediate_wire <<= Slice(0)(Slice(Range(2:1)(Slice(Range(3:0)(a)))))

Type changes along the way are tolerated.

For Composites, member access happens through `__getattr__` instead of `__getitem__`, but the logic is the same.

This is the easy stuff. The complexity comes with LHS expressions.

## LHS expressions

When we assign to a slice of a wire `a[3:0]` or `a[3]`, what we really mean is a portion of a `Concatenate` instance. Or, if we really wanted to, simply a special Module of our choosing. Let's call it `PhiSlice`.

This is the only place, really, so far, where the data-flow has a convergence point, sort of a PHI-node, we'll need to create and insert. Thus the name 'Phi'...

So, when we see this code:

    a[3:0] <<= b
    a[4] <<= c
    a[7:5] <<= d

what we want to see is:

    a <<= PhiSlice(Range(3,0),4,Range(7:5))(b,c,d)

Again, types are not interesting, those will get resolved later. The *collection* of all the assignments and the maintenance of the ranges however *is* the job at hand.

What's more, due to the behavior of <<=, we will see a `__getitem__` call on `a`, followed by `__ilshift__` on *whatever that returns*. Same here:

    a[3:0][2] <<= b

Things get even more complicated with this:

    a[3:0] = b
    a[7:4][3] = c

Here we start seeing `__setitem__` calls for the last slice, instead an `__ilshift__` after the last slice. It can be supported, but maybe we should start by asserting in those...

## Combining the two.

Notice how both LHS and RHS contexts involve `__getitem__`. So, whatever that returns, it has to be a two-face entity. It should work as a `Wire` object in the sense that it should have `__getitem__` (and `__getattr__`) on it to support further sub-slicing as well as `__ilshift__` to support assignment.

It is not a `Wire` however in the sense that `__ilshift__` should start collecting the info for the future creation of `PhiSlice`.

`__getitem__` on `Junction` and this two-face entity also can't simply instantiate the `Slice` instance, because we don't yet know if we're on the LHS or the RHS. That instantiation will need to be delayed to the `convert_to_junction` logic.

Let's call this magical object `UniSlicer`

- `finalize_slices` is the thing in a `Junction` at the moment that deals with the creation of what should be a `PhiSlice` instance.
- this dealt with `raw_input_map` which is a name that gets us to a lot of pieces of the old infrastructure.
- `finalize_slices` assumed a net_type. We can probably call it earlier now. In fact it even called `_body`!!!!

# OTHERS
+ `JunctionBase.__enter__` and `__exit__` should add tests for things, like:

    with a as clk:
        with clk as b:
            c <<= b
            d <<= clk
        e <<= b # should be an error
        f <<= clk
    g <<= b # should be an error
    h <<= clk # should be an error

+ We should really discourage '=' style binding. It should really be reserved for the case of where no other means is possible: new locals. All others should raise an exception.

- We should *really* get generic inlining work. Right now all the slicer modules need to do terrible hacks to support them. With scopes being a thing (provided they are properly carried around) it should be relatively easy: we have names for any net that matters in the enclosing scope and should be able to generate names for the ones that are local only.

- Now, with the proper cascading of 'Slice' modules we don't collapse selections in a Number. Verilog doesn't like a[3:0][2:1][0] style sub-slicing, forcing us to break them out into individual wires. That's correct behavior, but not nice behavior. Maybe we should have a pass to collapse them?

- Number.Instance.PhiSlice probably could use a good rinsing.

- Number.get_slice and slice-simulation in general needs thorough review.

+ `Module.Impl.register_sub_module` should refuse registering of submodules outside `body`. - Actually, this is impossible to do. First, `register_sub_module` is called *lot* from outside the `body`. This is how all the adaptors get inserted. Second, `Module.__init__` checks if the parent is None. If it is, it starts a new Netlist and in essence, another top module. Now, while that is *probably* an error, it might not be. Technically, a single python program could have several top level modules alive at the same time. So, best to leave it as-is.

+ Now that `self.x = Select(...)` just adds an attribute to the instance, we need a tracer-like stage where we promote all those nets into the port collections and create an appropriate `Wire` instance for them. 

+ `create_named_port` is cumbersome, as we need to implement `create_named_port_callback`. Is there a way to simplify this logic?

- scoping and context needs a re-think. It's an ever expanding mess of confusion.
+ On a related note, BoolMarker and ScopedAttr seem to be redundant. Choose one and migrate!

- Right now in Module._body we only test for new attribute names for promoting wires. That is, if the attribute existed, but changed, we won't create a wire for it. Maybe that's the right behavior, not sure.

- We shouldn't try to sort modules into groups in `_post_elaborate`. We should rely on string-compare of the generated module body to group instances.

## Hybrid LHS slices

On hybrid LHS slices, the clue to delimiting the key-chain to individual sub-sections is that each collapse-able section *ends* with a single element, unless it's the last one. So, for example:

    a[4:2][1][4:5][0]

has two sections. The first `[4:2][1]`, which selects down to a[3]. If a was an array of numbers, now, we're down to a wire, on which, the second section `[4:5][0]` ends up selecting element 4. Another example:

    a.m[4:3].c

This is invalid, because [4:3] doesn't select down to a single element, so .c means nothing.

The funny thing is, that if we really wanted to, we could do the collapsing and sectioning even without type information. It is probably still better if we left it up to the types to deal with this though.

## Interop

We should think about interop with migen (Amaranth) and LiteX libraries.

## Simulator

- We should not inject properties into XNets and Junctions and what not. Just like Netlist, we should maintain outside hash tables. This is especially tricky with `sim_value`, which is a *property* on the `Junction` and is used within the simulated version of operators, such as `__and__` and `__plus__`.
- Netlist now populates Junction._xnet. This is ugly, and should not happen, yet (see above) `sim_value` depends on it.

# Error messages

- The whole recording of the context for an error is busted big time.
   