# Modules defined in Silicon


composite.py:    class ToNumber(Module):
fsm.py:class FSMLogic(Module):
gates.py:class Gate(Module):
module.py:class GenericModule(Module):
number.py:    class MemberSetter(Module):
primitives.py:class Select(Module):
primitives.py:class _SelectOneHot(Module):
primitives.py:class Concatenator(Module):
primitives.py:class Reg(Module):
rv_buffers.py:class ForwardBuf(Module):
rv_buffers.py:class ReverseBuf(Module):
tantos@dell-laptop:~/silicon/silicon$ grep "(GenericModule" *
adaptor.py:class Adaptor(GenericModule):

composite.py:    class FromNumber(GenericModule):
composite.py:    class Accessor(GenericModule):
composite.py:    class InterfaceAccessor(GenericModule):
composite.py:    class StructCombiner(GenericModule):
constant.py:class ConstantModule(GenericModule):
enum.py:    class EnumAdaptor(GenericModule):
fsm.py:class FSM(GenericModule):
member_access.py:    class GetSlice(GenericModule):
memory.py:class _Memory(GenericModule):
memory.py:class Memory(GenericModule):
module.py:class DecoratorModule(GenericModule):
number.py:    class Accessor(GenericModule):
number.py:    class SizeAdaptor(GenericModule):
rv_buffers.py:class Fifo(GenericModule):
rv_buffers.py:class DelayLine(GenericModule):
rv_buffers.py:class Pacer(GenericModule):
rv_interface.py:class RvSimSource(GenericModule):
rv_interface.py:class RvSimSink(GenericModule):
rv_interface.py:class RvController(GenericModule):

# Modules

`Module`s are the basic build-blocks of Silicon, and the main construction mechanism to create a design. They are very similar to Verilog modules, so if you are familiar with that concept, you are going to feel at home.

If not, Modules package up a self-contained piece of functionality. They can be as complex as a full chip or as simple as an 'and' gate. Modules are comprised of a set of inputs and outputs, called `Port`s. Modules also express their behavior: how they react to input stimuli.

Modules are 'types'. They need to be instantiated to represent actual HW. Modules inherit from the `Module` or `GenericModule` class.

The most common way to describe the ports of a module is to simply list them as static members:

    class MyAdder(Module):
        a_in = Input(logic)
        b_in = Input(logic)
        c_in = Input(logic)
        s_out = Output(logic)
        c_out = Output(logic)

As said before, modules also have to describe their behavior. In almost all cases, this is done by creating a module hierarchy; by filling the inside with instances of other modules. This is achieved by overriding the `body` method of the base-class:

    def body():
        self.s_out <<= xor_gate(self.a_in, xor_gate(self.b_in, self.c_in))
        self.c_out <<= (self.a_in & self.b_in) | (self.a_in & self.c_in) | (self.b_in & self.c_in)

In this example we see two ways of instantiating submodules: the first line explicitly calls out the module (the `xor_gate` in this example) to be instantiated. The second line uses boolean operators, but the end result is the same: some `and_gate` and `or_gate` instances get created.

On top of creating the submodule instances, we also specify their connectivity. As an example, the first `xor_gate` instances' two inputs are connected to self.a_in and the output of the second `xor_gate` instance respectively.

We've created a mini netlist for our module. By doing that, we've fully specified the behavior of our module: for any set of inputs, the value of the outputs could be determined as well.

Of course, real-life modules are way more complex than this, and contain state as well (in the form of `Reg` instances), but the principle is the same.

# Nets and their types

Modules have ports. Ports can be inputs, outputs or uncommitted; no bidirectional ports are supported in Silicon. Modules are instantiated in a hierarchy, and their ports are connected to one another as well. Connecting ports together is called 'binding'. If a set of ports are bound to one another, they are forming a net. Each net can have at most a single driver or source, but can have any number of sinks.

Nets exist strictly within a single level in the module instantiation hierarchy. This means that they either are driven by an input of the enclosing module or by an output of a submodule. Sinks can be outputs of the enclosing module or an input of a submodule.

## Wires

On top of inputs and outputs, Modules can also have internal wires. These are different from Nets in that they only provide a naming alias (and potentially typing hints) to the framework. They themselves are nodes on a net just as inputs and outputs are.
## Uncommitted ports

In some corner-cases it is beneficial to not specify the direction of a port when it's defined. For instance, imagine the following expression:
`a[3:0]`, where `a` is some `Junction`. If this expression appears on the left-hand-side of a bind operation: `a[3:0] <<= b`, it is treated as a partial assignment to `a`. If it appears on the right-hand side (`b <<= a[3:0]`), it is a slice operation. Partial assignments get collected into a single Module, and each of the assignments get converted into an input port on them. Slice operations are converted into slice modules, where each slice is turned into an output port.

The point is that when the `[]` operator is evaluated, it's not yet known if it's going to appear on the right- or the left-hand side.

> To be more precise: it isn't clear if there are cascaded `[]` operators in the form of `a[3:0][1:0][0]` for instance.

Because of that, a dummy module is created with two uncommitted. One for the whole net (`a` in the above example) and another for the result of the `[]` operation. If this module ends up being used in the left-hand side context, the ports get changed into output and input respectively. If it ends up being used in a right-hand-side context, the ports are changed into input and output instead.

> NOTE: I'm not sure, this is useful: we still need to collect all the partial assigns and create a single module, so it's unclear how much this concept simplifies things. What I'm really after here is a Phi-node concept: the LHS use eventually creates a type of Phi-node. If we were to ever deal with if-statements, those would create similar constructs.

## Constructing nets

Initially, when a modules `body` is evaluated, very little is checked about the validity of the connections. Source-sink relationships for instance are not validated, every connected net is simply thrown into the basket of a net.

After the evaluation of the `body` is complete, a pass scans each net and select the driver. If multiple drivers are found, an error is raised. Once the driver is identified, the graph of the net is re-arranged such that the driver sources all other junctions in the net, and each sink directly sinks from the driver. This allows for the re-use of sinks as drivers of other junctions, most importantly, it allows for the use of the enclosing Modules output ports to be used as inputs to expressions (which Verilog allows, but VHDL doesn't).

> NOTE: at this point, net types are not propagated and coalesced yet. That means, that the source might not have the same type as some of its sinks. Later on, an implicit adaptor will be inserted for those cases and the net will be broken into pieces. The re-arranging of the connectivity graph of the net means that multiple implicit adaptors could be inserted, where-as the original connectivity graph would need fewer. What's important to note is that since only implicit adaptation is allows, and implicit adaption means that we only allow the expansion of the represented value-space, the change in topology doesn't result in a change of behavior; unless of course the user defines a custom type with a botched `adapt_from` implementation, but that's a different topic.

## NetTypes and type propagation

Each net has a single type, a `NetType`. It could be as simple as a `logic`, which is just a one-bit wire. It could also be a bundle of wires, say a 32-bit integer, denoted as `Unsigned(32)`. It could also be more complex, such as a `Struct` or an `Interface`, carrying more complex information. Whatever the type is, in the end, it will be represented by a set of wires carrying electrons from one place to another, which is more or less the only restriction on what `NetTypes` could be.

Initially, when the netlist is constructed, only connectivity is established. That is to say that type-compatibility is not checked or ensured.

Once a modules `body` finished executing, the type-propagation phase takes over. During this phase, the framework attempts to propagate type information from sources to sinks across nets. This process can have several outcomes:

 - If the sink has a type, the sources type might need to be adapted (using `implicit_adapt`) to the sink type. This process would instantiate an 'adaptor' class instance, and brake the net in two.
 - If the sink doesn't have a type, its type is set to be the same as that of the source.
 - It's also possible that the adaption attempt fails, in which case an error is raised.

Once type-propagation completes, some submodules might have all of their inputs 'specialized'; that is to say, they have type information. These sub-modules are ready for instantiation, and their `body` can be called recursively.

The consequence of instantiation is that the submodules outputs gain their types, become specialized. This gives type-propagation new opportunities to determine (or coalesce) types for more nets; which in turn will allow for more submodule instantiation.

This (recursive) process continues until no more progress can be made. This can be for one of two chief reasons:
 - all nets are fully specialized, the module is properly instantiated
 - some nets are not specialized, in which case the framework raises an error.

Obviously the previously described process only works if the source of at least some nets has a type defined. An important piece of information is the following: a module only gets instantiated - its `body` method is only invoked - if all its input ports are specialized. s.

> DO WE NEED THIS? WHERE TO PUT IT, IF SO? These inputs are sources to submodule ports within the module, so their types can be propagated. In most cases, this step results in some submodules having all their inputs having types. The `body` method of these submodules can be called, and type-propagation can be completed in the submodule recursively. When this recursion returns, the outputs of the submodule have well-defined types which - again - are sources for some net in the enclosing scope. Type propagation can continue with those nets. Eventually, the process either finds a type for all nets, or realizes that it can't make any forward progress, in which case an error is raised.

Why would there be cases when no forward progress can be made? The simple answer is: loops. One way of thinking about the description of the behavior of a module (the netlist that `body` creates) is that it is a data-flow graph. As long as that graph is an acyclic one (a DAG), type-propagation should terminate. However, not all data-flow graphs are DAGs. As soon as we introduce state into the module, we can have feedback edges in the graph. Imagine the following simple counter:

    class Counter(Module):
        clk = Input(logic)
        set = Input(logic)
        val = Input(Unsigned(8))
        cnt = Output()

        def body():
            self.cnt <<= Reg(Select(self.set, self.cnt+1, self.val), clk_port=self.clk)

To understand what's happening here, it's important to note two things:

 - `Input` and `Output` can be created without any types, as in `cnt` in our example
 - `Select` is a binary encoded mux. For our purposes, if `set` is 0, it'll output `cnt+1`, otherwise `val`.

What is the data-type of the output of `Select` though? Well, it must be the type of... the common type of `cnt+1` and `val`. A common type is something that can represent all values from - in this case - `cnt+1` and `val`. On the one hand, `val` is easy: it's an 8-bit unsigned integer. But what is `cnt+1` or `cnt` for that matter? It's the output type of `Reg`, which is presumably the same is its input type. This input type is the output type of `Select`, which is - as we've said before - the common type of `cnt+1` and `val`. We have a loop here, and the type-propagation algorithm will get stuck.

To help it out, we can do the following:

    class Counter(Module):
        clk = Input(logic)
        set = Input(logic)
        val = Input(Unsigned(8))
        cnt = Output(Unsigned(8))

        def body():
            self.cnt <<= Reg(Select(self.set, self.cnt+1, self.val), clk_port=self.clk)

In this case, the type of both inputs into `Select` are known, so its output type can be determined: it is going to be a 9-bit integer with a restricted value set from 0 to 256. That is also going to be the type of the output of the `Reg` instance.

At this point however, we run into trouble: we're trying to assign a 9-bit (albeit restricted) integer to an 8-bit one: `self.cnt`. While type-propagation will attempt to implicitly adapt these types, it'll fail. So even more help is needed:

    class Counter(Module):
        clk = Input(logic)
        set = Input(logic)
        val = Input(Unsigned(8))
        cnt = Output(Unsigned(8))

        def body():
            self.cnt <<= Reg(Select(self.set, Unsigned(8)(self.cnt+1), self.val), clk_port=self.clk)

With the type conversion, we're finally good. In fact, this solution would also work:

    class Counter(Module):
        clk = Input(logic)
        set = Input(logic)
        val = Input(Unsigned(8))
        cnt = Output()

        def body():
            self.cnt <<= Reg(Select(self.set, Unsigned(8)(self.cnt+1), self.val), clk_port=self.clk)

# What I want for ports.

Ports are types. In fact, they are a type with multiple-inheritance. They both subtype their Input/Output etc. port type as well as their NetType. So, for instance:

    my_input = Input(Signed(16))

creates a new type (if it doesn't exist already), which is roughly speaking `Signed16.Input`, which inherits from both `Signed16` and `Input`. my_input is then an instance of that type.


# More on types: Number and its relatives

Net Types MUST have a __new__ implementation, that creates an instance if no parameters are passed in. That is, because Port types use multiple inheritance in a way that JunctionBase.__new__ will end up calling net-types' __new__ with no parameters.

This of course should be OK, as parametric net-types are implemented using NetTypeFactory subclasses.

BTW: why aren't parametric types NetTypeFactory instances, instead of subclasses? That makes NO SENSE, except for maybe hiding some types.
# Type conversion

There are several ways to achieve type conversion. Probably the simplest way is to use the name of the target type:

    my_wire = Wire(Unsigned(4))
    another_wire <<= Unsigned(16)(my_wire)

In the previous example, we've cast our 4-bit integer into a 16-bit one. More complex conversions are also possible of course. An exception is raised if the conversion cannot be performed.

The same effect can be achieved by the `cast` call:

    my_wire = Wire(Unsigned(4))
    another_wire <<= cast(my_wire, Unsigned(16))

There are a set of functions available to have a bit more control over the type of conversion performed:

    def implicit_adapt(input: 'Junction', output_type: 'NetType') -> 'Junction':
    def explicit_adapt(input: 'Junction', output_type: 'NetType') -> 'Junction':
    def cast(input: 'Junction', output_type: 'NetType') -> 'Junction':
    def adapt(input: 'Junction', output_type: 'NetType', implicit: bool, force: bool) -> 'Junction':

While the actual rules of what is possible and allowed depends on the various `NetType` implementations, the following general rules apply:

*Implicit* adaption happens when two nets of different types are bound together. For instance, if a source has a type of Unsigned(4), while the sink has a type of Unsigned(8), a simple zero-extension is needed. Implicit conversion is only successful if the full range of the source can be represented by the sink. Both the source and the sink needs to have the same generic type, `Number` for instance. Some types, such as `Struct`s don't support implicit adaption at all.

*Explicit* adaption only happens, if the user asks for it. Explicit adaption still requires the representable values to be compatible, but allows for the change of the type, for instance from a `Number` to an `Enum` or a `Struct`. You can think of an explicit adaption as taking the input value, converting it a `Number`, then re-interpreting that value as the output type.

*Cast* is the most forgiving of all adaption schemes: it can do everything that explicit adaption can, but also allows for truncation of the values to fit within the output value range. For instance, it's not possible to implicitly or explicitly adapt an `Unsigned(8)` to an `Unsigned(4)`, but it's perfectly valid to `cast` it.

These have very few uses within Silicon at the moment.

`implicit_adapt` is used only in `set_source` to bind mismatched ports together.

`Memory` uses `explicit_adapt` to get the bit-vector representation of the data-port types as the underlying memory instance only understand `Number` types.

Since call-style casting is supported, `cast` is also used within the `__call__` of `NetType`.

`adapt` is used by `Struct` in `adapt_to` and `adapt_from` to create a Number representation of itself. Since `adapt` is the grand-father of all other conversion functions, they use it as well.

The internal implementation of `adapt` makes use of the conversion-methods defined on the various `NetType` objects themselves: `adapt_from` and `adapt_to`.

Every type is expected to implement these methods, but a default implementation is provided in the `NetType` baseclass. They are dual-purpose methods, used both during elaboration and simulation. In the elaboration context, they should return a `Junction`. During simulation, they should return a `NetValue` (:::TODO or whatever this morphs into). If the conversion is unsuccessful, they ought to raise `AdaptTypeError`

`adapt` first tries `adapt_from` and then `adapt_to` if needed. This way either type of the conversion can implement adaption, but the LHS gets priority.

For elaboration purposes, the internal implementation of `adapt_from` and `adapt_to` usually uses an 'adaption module'. These are simple (maybe generic) `Module` classes, that encapsulate the conversion between the two types. For simulation purposes, the functions simply calculate the converted value, encapsulated in an appropriate `NetValue`-derived instance and return it.

# Net values

# Constants

Constants need special treatment. Consider the following code-snipped: `a <<= 3`. What is the `NetType` of 3? And who is the source? Where is the associated source port?

Silicon deals with these problems, using the `ConstantModule` class. This module has a single output port, and as a generic parameter, an output type and an output value (in the form of a `Constant` instance).

There is a lookup table, called `const_convert_lookup`, which contains conversion functions. This table is indexed by the type of the constant (`int` or `bool` or `str`) and contains a callable instance. This callable gets the constant value and a type-hint (which can be `None`). It supposed to return a `Constant` instance.

Supported types can register conversion functions. For instance `Number` knows how to deal with `int`, `float`, `str` and `bool` types, so it registers a function each for those. `Enum`s need to be able to handle their own constants, so each `Enum` instance registers a new conversion function, just for their own underlying Python `Enum` type. Since these functions return an appropriately interpreted value and `NetType`, they are used for both elaboration and simulation contexts. The `ConstModule` class is obviously only instantiated for the elaboration context.

There is a very important distinction here: constants are not necessarily just the number `3` as above. They could be meta-programming values, essentially anything, that's fixed during RTL generation.

:::TODO: we should standardize on how these things are dealt with. For instance, `Constant` could always contain a `NetValue` as the value field.

# Assignments and binding

Binding is the process of connecting a source to a sink. Assignment is the equivalent, during simulation. Both are in the form of `a <<= something`. The left-hand-side of such operations can be many things:

- An output port
- A constant
- :::TODO: what else?

During elaboration, we have to make sure that the left-hand-side is converted to a `Junction` instance. During simulation, we have to make sure that the left-hand-side is a `NetValue` instance. This job falls on the `convert_to_junction` function. This is where `ConstantModule`s are instantiated during elaboration. The easiest way to explicitly create a `ConstantModule` instance is by the `const` function.

`convert_to_junction` does quite a few things, but mostly it is concerned by:

 - Causing no harm, that is: if the supplied thing is already of the appropriate form (`Junction` or `NetValue` instance), it simply returns it.
 - Attempts to create a `Constant`, then either a `ConstantModule` or a `NetValue` from that
 - If that fails, it attempts to convert the input to something (an `int`, a `bool` or a `str`) that it knows how to deal with. This latter trick is needed in case someone uses special constants in the code, for instance NumPy values, that can reduce to `int`s.



Internally, these methods usually instantiate a conversion `Module`, which have a single input and a single output of the appropriate types. These `Module`s then internally know how to generate RTL for the requested type conversion.

The following `Modules` are used for this purpose:
 - Struct.FromNumber
 - Struct.ToNumber
 - Enum.EnumAdaptor
 - Number.SizeAdaptor

> BUG: NetType.__eq__ and __ne__: these should not be defined. They should be 'is' and 'is not'.


# NOTES AND TID-BITS

What I'm starting to tend towards is this: `Junction` is really a future promise of a value. `NetValue` is an actual value. There is something, called `convert_to_junction` which is the focal point to convert anything we understand into a `Junction`. Now, this is only prepared to work in the elaboration context, but maybe that's wrong. Maybe what we would need is (a version) which can work in either.
In simulation context, it would convert anything into a `NetValue`. `Junctions` would return their sim_value member, constants would get converted to a `NetValue` object. Or something...

If we get to a point, where the return value of this `convert_to_junction` variant is always an object, we can control the methods on it. With that, `adapt` and many many other things could be universal.

It appears to me that `const_convert_lookup` and `sim_convert_lookup` should not be needed. What we need is `adapt` being better at, well, adapting. It should accept anything as an input, not just a junction. Then, it would use the target type (`output.adapt_from`) to do the actual conversion. For this to work however `adapt_to` and `adapt_from` would need to know the context. That's hard, because `adapt` itself doesn't know it. I'm thinking of giving up and having a global `context` however unsavory that is.

Well, actually, maybe not all that bad: we can have a context stack. That could be global, yet still allow for some decent management of contexts.

I believe `adjust_precision_sim` should check for bounds and whether it was a force-convert. BTW: how to do force-convert in a range-based type-system????

I have a headache: there are two contexts here: one is managed by a context stack, and one is managed by `module._impl._in_elaboration`. This is obvious madness and needs to be cleaned up. I prefer the context stack approach because we need to know these things in 'adapt' now, but I hate globals.

OK, so here's what I will do: I will - for now - nuke the elaboration context variable as well as the current dumpster-fire of a context stack. Instead, I'll create a new, global context stack and port everything over to that. At a later point, this could be revisited again, but at least it will be consistent.

Need to look into ContextMarker, also set_context and it's recursion.
