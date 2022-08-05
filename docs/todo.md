# Introduction of Net objects

`Junction.set_net_type`, when the net type was set to something (not None) used to walk the `sources` list and `sink`, re-setting the connectivity, by calling `set_source` in the appropriate way. This in turn would have inserted the appropriate `adaptor` instances if needed. In the new world, this is going to happen in a later phase, but the invocation of `set_net_type` would need to be scanned to make sure we don't use that to force the insertion of an `adaptor`.

+ IMPORTANT BEHAVIOR CHANGE!!!! `set_source` used to remove itself from the sink it was driven by, if one existed. This functionality doesn't
quite work now as we don't necessarily have source-sink info on the nets when `set_source` is called. Now, under the same circumstances, the old and new nets are merged.

+ `bind` is gone and `set_source` doesn't try to be smart about scope determination: it needs to be specified. `auto_bind` also needs a scope parameter.

+ Naming inconsistency: `Module.Impl.parent` should be `parent_module`.

+ `convert_to_junction` should be used very sparingly: it mostly should be in `set_source`.

+ Nets are now just one 'level' of an Xnet: one source and its sinks. This is very similar to what we used to maintain, except we keep it outside and it allows for late-assignment of the source. As such, we allow reading of outputs inside modules.

# Nets: a new approach

After all, I think what I want is a netlist, that is the actual graph representation. That is to say, we have two classes of objects:
- NetEdges, which have one source and one sink, plus a scope and a potential type attached to them
- NetNodes, which are essentially Junctions, renamed.

This way we can have an output for instance driving sinks both inside and outside its module, no need to re-purposing its driver. This can be re-written, if needed during RTL generation. The only limitation is: outputs can't appear on the LHS outside and inputs on the LHS inside a module. All other connections are legal.

We can have three ways of storing (and looking up) nets:

    my_port.parent_module.nets_by_source[my_port]
    my_port.parent_module.nets_by_sink[my_port]

    my_port.sources[my_port.parent_module]
    my_port.sinks[my_port.parent_module]

    Netlist[my_port.parent_module].nets_by_source[my_port]
    Netlist[my_port.parent_module].nets_by_sink[my_port]

The last one doesn't require any knowledge of the nets inside the NetNode object or a Module for that matter. It appears to me that all require three hash lookups, so there shouldn't be a huge performance delta. That is to say: I'm going with the last approach

## More on Nets

Here's a new concept: the connectivity in the end of an XNet is a tree. As such, each (non-terminal) node has a 'previous' (source) and a set of 'subsequent' (sink) nodes. Let's call a Net one `Junction` and all its sinks. A `Junction` is then part of at most two Nets. One as a sink, another as a source. Each Net though *does* have both a source and a set of sinks. Each Net also has a unique scope, the `Module` instance that contains the net.

Merging Nets is not really a thing in this world, as long as we maintain them as we go.
Splitting Nets is also easy, in fact the current algorithm should work.

Since we always know who is the sink, we can more or less maintain Nets as we go, we just don't necessarily know which of the many junctions is the source.

Here is the problem though: if we don't know whether a Junction is a source or not for a given Net, how can we tell which of the two possible ones any of their connections belong to?

I reality thus, we'll *have* to find a way to figure out who is a source and who is a sink in any given net.

Our main vehicle now to making connections is 'set_source'. Which is a bit of a misnomer, as it establishes that `self` is a *sink* of something. That something can be the following:
1. A wire. In that case we know that that's the source.
2. An output of a sub-module: it is the source
3. An input of a sub-module: it is *not* the source. Whoever ends up driving that, is the source. We can register both sides of `set_source` as sinks though and worry about the real source later.
4. An input of the enclosing module: it is the source
5. An output of the enclosing module: same as (3). We *know* its not the source.

There are two classes: 1,2,4, when we have source-sink relationship and 3,5 where we have a sink-sink relationship.

Let's look at 1,2,4 first:
- if source already is part of a Net as a source, sink is not as a sink, we add sink to it.
- if sink is already part of a net as a sink, and source is not as a source:
   - If the net already has a source --> err out
   - Otherwise add source
- If neither are parts of nets of the proper kind: create a net, add them as appropriate
- Both are part of their respective nets of the proper kind: we'll have to merge the two nets. Again, if we end up with multiple sources, err out.

Now, for 3,5:
As a pre-req: we'll treat both Junctions as sinks, so it doesn't matter which is which
- If neither are part of nets as sinks, create one and add them
- If exactly one of them is part of a net as a sink, add the other as a sink
- If both are part of nets as sinks, merge the nets. If multiple drivers are the result, err out.

- `convert_to_junction` should use `create_submodule`, which of course means that `convert_to_junction` would also need a scope.
  Maybe not. It actually extract the scope from the static scoping stack. That might be sufficient, especially since `convert_to_junction` is used in simulation too, where it doesn't need a scope and it might be hard to provide one. 
# Interfaces

We have an issue with the whole `Net` concept: since `Net`s don't maintain actual topology, just a source and a bunch of sinks on the same hierarchy level, they have an issue with interfaces: Interfaces don't quite know how to deal with bifurcated topologies. So:

    a <<= interface_generator()
    b <<= a
    self.my_output <<= b

is perfectly fine, but it'll have issues. Now, here's the saving grace: interfaces should never care about `wire`s. Those are just names attached to a net, not really sources or sinks. As such, they shouldn't matter. But! Doesn't that mean that wires should be a different category altogether?

# Idea for a project

Creating yet another soft-core processor is fun and all, but isn't a good project. However, having an open-source alternative to Tensilica or Codasip might be something of interest. Though here's the problem: I don't think we can make any significant inroads into the ASIC world. And in FPGAs, these custom ISA processors are rather silly... Or, is it?! It is certainly silly the way it's done in ASICs, but there's another way to think about it: one can add/remove accelerators to the ISA with dynamic partial reconfiguration to a soft-core. Now, *that* is interesting!!!

So, maybe that should be the project: create a customizable ISA soft-core, where the custom ISA can be swapped in dynamically. Have all the auto-generated compiler/simulator/debugger working too. And, and!! do it within Silicon, because that's a clear use-case for it.

As far as the base ISA goes, unfortunately, we'll have to go with Risc-V though, if we want to have *any* traction. Brew will have to clearly remain a separate project.