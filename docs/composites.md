# Composites

Composites are a bit of a mess at this point.

What we want is an opaque type, something that doesn't need its influence spreading all over Silicon, like cancer.

What we want is Composites to have their members, included inside. For now, I'm going to go even as far as require that members are accessed through index notation:

    pixel["R"] <<= 34
    pixel["G"] <<= pixel["B"] + 1

That sort of stuff. When generating RTL, we somehow still have to be able to generate individual wires for the constituents of a composite.

Doing the above now should be possible with the UniSlicer object: it can take elements and concatenate piece-wise assignments, even handle hierarchies (maybe... eventually).

What's tricky is `reversed` members. Now, here's the trick though: `Composites` with reverse members have very restricted topologies. They are essentially point-to-point links, but the netlist actually could be, in fact in most cases, will be more complicated. There are input and output ports passing them up- and down- the hierarchy, eventually terminating in ... something.

What is curious is that `UniSlicer` decomposes into a `Slice` Module when used in a RHS context. It registers a partial source (through `set_partial_source`) when used in a LHS context.

These partial sources eventually will be turned into a `PhiSlice` instance in `Junction.finalize_slices`.

So, what about reversed members?

    class MyIf(Interface):
        f = logic()
        b = reversed(logic())

    class A(Module):
        p = Input(MyIf)

        def body(self):
            p["b"] <<= p["f"]
    
    class B(Module):
        p = Output(MyIf)

        def body(self):
            p["f"] <<= Reg(p["b"])

    class top(Module):
        def body(self):
            A(B())
    
So, what actually is happening?

In `A`, we'll generate a `Slice` for 'f' and `PhiSlice` for 'b'. In `B` the opposite will happen. `Slice` will end up calling `get_rhs_slicer`, but the problem is that the port directions are wrong: in `B`, we have an output port (`p`), which drives the input of a sub-module (the `Slicer` instance). I think that'll result in all sorts of chaos.


Actually, it's a NO on two accounts: first, the topology is complex, even if only `Slice` objects are involved: each member access generates its own `Slice`, eventually leading to many sinks on the same XNet. Second: it's not just `Slices` that can be involved. Think about a `Complex` number. Well... on that front, by the time we land on primitives, it is through slices, so maybe that part is still true.

BTW we should test if we properly protect against shananigans like this:

    a = Output(Unsigned(8))
    b = Input(Unsigned(8))

    ...
    self.b[3] <<= 3 # Should not work
    x = self.a[3] # Should work
    self.a[2] <<= y # Should work
    y = self.b[2] # Should work

So, this all blows up as it should. It blows up when we create the `PhiSlice` module and try to set it as the source of `self.b`. The protection against it is in `InputPort`. I'm thinking, maybe we should have another method, `set_reversed_source` to indicate that we're setting the source for the 'reversed' part of a type. This method could be implemented in the `NetType`-derivative itself, so normal types just raise an exception. The test for this is `test_basics:test_invalid_slice`.

As of now, the query of an output slice generates the RTL we want, because Verilog is allowing for it. For VHDL, we might have to do more surgery.

For now, the new composite is going to be called `Aggregate` to make it unique. Once it's done, it'll get renamed (maybe).


## TODO:

- MEMBER_DELIMITER must die: it should be part of BackEnd
- setup_junction should go to the dump too
- RhsSlice.generate_inline_expression: how does it work with nested aggregates? Needs a test.
- PhiSlice and the rest: we need to differentiate reverse assigns, I think. That needs to reverberate through the whole framework...
- Maybe in PhiSlice.body, where we know the outside topology, we can figure out if we're driving the reversed section of an aggregate...
- PhiSlice is mighty broken with nested Aggregates. It's broken for everything at the moment of course, but even more so for nesting.

Thins are not as dire though:

A PhiSlice creates a RHS expression, to be assigned to the aggregate. The LHS name for an aggregate (right now) is just a concatenation of all the (closure of the) members. So, when assigned, it should just work.

Sub-aggregates also work, as the generate (on the RHS) an concatenation that becomes part of a larger concatenation.

IF sub-aggregates are broken off to ports (such as the 5 AXI sub-buses being directed to 2 different sub-modules over 5 individual ports), these sub-aggregates get names, thus their RHS expression becomes a concatenation of those name in the concatenation. All still is probably fine.

Extraction of an element of an aggregate (a RhsSlice) is more problematic: since the names of the underlying wires are generated from the colsured names, the RhsSlice would need to generate a concatenation for sub-aggregates. It still could be done, I think without considerable problems. However, nested selector (large.small.piece). For that, interaction between the nested RhsSlice items is needed. Otherwise the generated RTL will get incomprehensively convoluted.

* Maybe what we need is a way to treat expressions as list of expressions instead. This would allow for the generation of piece-wise assignment to aggregates, more akin to what's happening right now.
* This doesn't help with nested RhsSelectors. So, let's see an example!

    class S1(Aggregate):
        m11 = Unsigned(8)
        m12 = Unsigned(8)

    class S2(Aggregate):
        m21 = Unsigned(8)
        m22 = S1
    
Now, what does this mean?

    s1 = Input(S1)
    s2 = Input(S2)
    t1 = Wire(S1)
    w1 = Wire(Unsigned(8))

    t1 <<= s2.m22
    w1 <<= s2.m22.m11

The generated RTL should be something like this:

    assign t1_m11 = s2_m22_m11;
    assign t1_m12 = s2_m22_m12;
    assign w1 = s2_m22_m11;

The first RhsSlice takes advantage of the expression lists: the names of the individual wires are known (???). But the cascaded selectors in the second one would like to do this:

    assign u3_output_m11 = s2_m22_m11;
    assign u3_output_m12 = s2_m22_m12;
    assign w1 = u3_output_m11;

Maybe the right way of thinking about this problem is to introduce a lowering pass that breaks up the aggregates into smaller chunks. That kind of framework would generally be useful, so developing it would help a lot.

The problem is that in order for that to work, I would need to extract all the netlist info from the constituents of the ... well, netlist, and put then in a separate object. So, _source and _sinks and all that jazz would need to be externally stored. This is problematic for the simple reason that in many cases (hello operator overload!) the auxiliary information cannot be passed in to the functions. And globals are undesirable for a different reason.

Another way of thinking about this is to make sure that netlists can be deep-copied, which would allow the creation of several copies. In that setup, one could safely in-place modify the structure because one could also have saved off copies of previous passes. This approach would need minimal changes, but would make user-defined objects more restrictive: if someone puts a reference to anything sensitive inside a Module for instance, the deep-copy procedure would render the result at least questionable, if not straight up invalid. (In other words, I hate deep-copy).

There is a third approach:
  1. we keep the info on the Modules and Junctions while we go through the bodies.
  2. We have a pass that extract that info into an external Netlist object
  3. We allow (provide) a function to make copies of Netlist objects
  4. Now we can introduce new phases that mutate the Netlist, such as:
     1. Remove unused Nets
     2. Bisect interfaces into reverse and forward structures
     3. Blow up aggregates into individual wires
     4. Merge and propagate PhiSlices and RhsSlices
  5. As usual with compilers, as long as these manipulations don't change the underlying Netlist data-structure (in type, not in content), most tools and functions would continue to work on any of them.

All in all, we start to really build a compiler here. We really are building and manipulating an SSA data-flow graph...

So, what could go wrong here? The problem is that Aggregates - again - are pretty deeply integrated into the library. It's not like they could have been 'tacked on' as an extension. Still, this is - potentially - a much better framework to deal with the problem or any (many) other problems that will come up in the future. What could come up?

  1. Memories: these bastards are very intrusive, especially of the ASIC kind.

Let's think about the transformations we want to support on the netlist. This list should also include all the things we do *during* what is currently elaboration!

  1. Create new `Moodule` instance inside other module (or top level for that matter)
  2. Create `Input`/`Output` port on module instance
  3. Create `Wire` junction inside module
  4. Set the source of a junction
  5. Set the net type of a junction

More complex operations:

  1. Create adaptor instance to resolve type-conflicts
  2. Propagate net types
  3. Create `PhiSlices` (Phi-nodes in general)
  4. Create `XNet`s from individual source-sink relationships
  5. Create and de-conflict symbol-tables (per scope)
  6. Mark `XNet`s as 'hidden' or something (XNets that are only for documentation, but don't participate in SIM/RTL generation)
  7. Duplicate `XNet` - allow name/type change
  8. Flip XNet direction.

This is still insufficient to deal with interfaces: we somehow have to tolerate multiple sources until we get to at least split off the reversed nets. It's also important that the source and sinks of the reversed and forward members are different, so we would need to manipulate those too.

The big question is: do we want to do all this in-place (mutable Netlists) or create new Netlists for each phase? Mutable is easier because we can still maintain back-links from Modules and Junctions to their Netlist. Immutable is nicer, because various stages of the operation can live side-by-side and without interference. I guess I'll try to strive for an immutable version, until that proves too hard. It's also possible to temporarily annotate the Modules and Junctions with Netlist links, then remove them when we want to 'freeze' the Netlist.

Here is what I've just realized: in some way, interfaces have the same problem as slices do: they introduce multiple drivers. The resolution of these multiple drivers is type-specific, but involves - just as with slices - the creation of PHI nodes to arrive at an SSA form. Here's the canonical example: imagine an interrupt controller: N lines for interrupt requests and a log2(N) wide acknowledge bus (with a valid or something). Now, if the interface is defines such that the request lines are forward and the response bus is reversed, then we have multiple drivers. Potentially all over the hierarchy.

So, I think we'll have to tolerate multiple drivers all the way to XNet creation and beyond. There should be a phase that converts the graph into SSA form. Until then, all drivers are maintained with an optional 'key' object that identifies their role somehow. This object could be None of course. For Numbers, we allow slices. For structs, we allow member setters. For interfaces, on top of all that, we allow reverse members. All in all, the resolution of these drivers is type-specific and of course could result in exceptions. For instance, we could define a wire-or-ed or wire-and-ed bus too. The result of the conflict-resolution, if successful is an SSA graph.

!!!!!!!! IMPORTANT !!!!!!!!!!!!

We should add a 'global' dictionary to Silicon. This dictionary instance is used to store all globals (and defaults to `globals()`). The idea is that if someone really wants to do a threaded implementation, they can create a TLS-based dictionary and set them on each thread to whatever they want it to be. The harder question is how to make Silicon itself multi-threaded, but that's no worth answering at this point: Python is pretty far from every being multi-threaded.

!!!!!!!! IMPORTANT !!!!!!!!!!!!

We should allow for default values for ports. These would define the value for unconnected ports. There's a type-specific fall-back of course, mostly None. We should also allow defaults for composite members and function-style module ports too (ideally using Pythons default value syntax).

## We're back!

So, the idea was, that composites start their life a single junctions. In order to support interfaces, we would need to merge `_source` and `_partial_sources`. Essentially allow - initially - multiple drivers. This, in a later phase would create problems of course. To resolve this, we would need a pass that converts the Netlist into SSA form, probably as part of XNet creation. This is where we would need to introduce PHI nodes. Some PHI nodes would be our PhiSlices, some would deal with the braking up of composites into individual wires. Maybe we could even offer a type-defined way of dealing with and resolving these conflicts.

The trouble starts with type propagation: if we allowed multiple sources, what to do about type conflicts? Notice though that we only need to propagate types, if the sink(s) don't have a type. I think at least that adaptor insertion can wait until the same pass that deals with PHI nodes.

As we merge `_source` and `_partial_sources`, we would need a key for each source, even if such keys are optional. We could say that type propagation is only supported through 'un-keyed' sources, that is sources with the key being None. If there are multiple source sources, we just can't propagate types and that's it. Maybe.

What to do with cascaded slices though? I *think* they are not a bit problem, but I'm not sure. They should become a partial source as anything else. They don't participate in type propagation, and they get resolved in the end as a PHI node.