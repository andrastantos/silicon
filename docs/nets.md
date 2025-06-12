# Introduction

In the previous chapter we familiarized ourselves with the `Module`s that make up one of the key concepts in Silicon. We've talked about various ways of instantiating sub-modules, building a hierarchy of them, even looked at RTL generation and simulation briefly.

However, we've skipped over the other big part of any digital design: the connection between the various module instances. The wires that create the connectivity and the ports that allows us to differentiate the various ways modules can be connected together. In this chapter we will fill that hole.

# Ports, Wires and Nets

Modules have ports. Ports can be inputs, outputs; no bidirectional ports are supported in Silicon. Modules are instantiated in a hierarchy, and their ports are connected to one another as well.

The most natural way - and the one we've seen in the previous chapter already - is to declare the ports of a module by adding static members to the module class. Let's pick up from our last example in the previous chapter:

```python
class FullAdder(si.Module):
    in_a = si.Input(si.logic)
    in_b = si.Input(si.logic)
    in_c = si.Input(si.logic)
    out_r = si.Output(si.logic)
    out_c = si.Output(si.logic)

    def body(self):
        xor1 = si.xor_gate()
        xor2 = si.xor_gate()
        and1 = si.and_gate()
        and2 = si.and_gate()
        and3 = si.and_gate()
        or1 = si.or_gate()

        xor1.input_port_0 <<= self.in_a
        xor1.input_port_1 <<= self.in_b
        xor2.input_port_0 <<= xor1.output_port
        xor2.input_port_1 <<= self.in_c
        self.out_r <<= xor2.output_port

        and1.input_port_0 <<= self.in_a
        and1.input_port_1 <<= self.in_b
        and2.input_port_0 <<= self.in_b
        and2.input_port_1 <<= self.in_c
        and3.input_port_0 <<= self.in_c
        and3.input_port_1 <<= self.in_a
        or1.input_port_0 <<= and1.output_port
        or1.input_port_1 <<= and2.output_port
        or1.input_port_2 <<= and3.output_port

        self.out_c <<= or1.output_port
```

In here, you see three input and two output port declarations.

Connecting ports together is called 'binding'. This is chiefly achieved by the `<<=` operator. You can also see a lot of them here as well. If a set of ports are bound to one another, they are forming a net. Each net can have at most a single driver, or source, but can have any number of sinks.

For instance, this line of our code created a single net:

```python
xor1.input_port_0 <<= self.in_a
```

We can also explicitly create nets in our design, using instances of the `Wire` class:

```python
xor2_result = si.Wire()

xor2_result <<= xor2.output_port
self.out_r <<= xor2_result
```

It is important to note though that you don't have to do this: the code we've started with is perfectly functional, even though it didn't define a single net. That doesn't mean those nets didn't get created, just that they are created implicitly. Or, to turn it around, all we did with the creation of the `xor2_result` object is to give a name to the otherwise already existing net. We can check that by looking at the generated code:

```verilog
////////////////////////////////////////////////////////////////////////////////
// FullAdder
////////////////////////////////////////////////////////////////////////////////
module FullAdder (
        input logic in_a,
        input logic in_b,
        input logic in_c,
        output logic out_r,
        output logic out_c
);

        logic xor2_result;

        assign xor2_result = in_a ^ in_b ^ in_c;
        assign out_c = in_a & in_b | in_b & in_c | in_c & in_a;

        assign out_r = xor2_result;
endmodule
```

Really, the change is only the naming of that net.

Nets exist strictly within a single level in the module instantiation hierarchy. This means that they either are driven by an input of the enclosing module or by an output of a submodule. Sinks can be outputs of the enclosing module or an input of a submodule.

Of course nets (through the module hierarchy) form larger constructs. For instance, a net, driven by an input of the enclosing module will have a driver in the module one level up in the hierarchy. Nets that are connected together and form the same physical connectivity tree are called `XNets`. Ultimately, `XNets` also have to have one driver and as many sinks as necessary, but they can also have 'pass-through' nodes in them; these are module ports that establish the connectivity between the nets comprising the `XNet`.

# Net types

Each net or `XNet` carries a piece of information from the driver to the sink(s). This piece of information is in the end encoded as a binary code on a set of physical wires, but logically, they are just values. What values are permitted and what are not needs to be specified though. The mechanism for doing so is to assign a 'type' to each net.

These types are described by classes that inherit from the `NetType` baseclass. Every net and `XNet` haves exactly one type. This is not to say that type-conversions can't happen, just that such type-conversions break the nets into pieces that indeed share the same type.

In fact, we've come across them already: all of our input and output ports have their type specified. Those are the `logic` references in the `Input` and `Output` constructs. `logic` in this case simply means a binary value. True or False, 0 or 1. In the physical world, they will be implemented by a single wire, in the generated Verilog RTL, they will be described as 'logic' signals. Silicon uses the same name as Verilog to make the concept familiar.

This of course is just the most primitive type there is and Silicon has a rich set of additional types to work with.

## Signed and Unsigned numbers

The next most important `NetType` is a number. This is a very rich concept and will take a while to get completely familiar with it. Something that to my knowledge doesn't exist in almost any language I've heard of. We'll get there, but we'll take small steps first. There are two helpers that can create nets of the more familiar type: N-bit integers. These can come in either the unsigned or the (2-s complement) signed form. Not surprisingly, they are called `Unsigned` and `Signed`.

They are very close to Verilog and VHDL vectors.

Let's look at another example:

```python
class VectorAdder(si.Module):
    in_a = si.Input(si.Unsigned(8))
    in_b = si.Input(si.Unsigned(8))
    in_c = si.Input(si.logic)
    out_r = si.Output(si.Unsigned(8))
    out_c = si.Output(si.logic)

    def body(self):
        full_result = si.Wire(si.Unsigned(9))

        full_result <<= self.in_a + self.in_b + self.in_c
        self.out_r <<= full_result[7:0]
        self.out_c <<= full_result[8]
```

You see here a vector version of our simple adder. Instead of dealing with single-bit inputs, both 'a' and 'b' are 8-bit integers now. The output is also 8 bits wide. Of course we still have our carry-in and carry-out signals, which are just single-bit wires.

The body also changed. For one, we are using the `+` operator. We also create a result wire, which is 9 bits wide. That of course is the case: adding two 8-bit numbers produces a 9-bit result. Then, we split this result into two parts, binding the low 8 bits to `out_r` and the MSB to `out_c`.

Pretty basic stuff on the surface. We can also generate RTL from this and convince ourselves that it does what we expect it to do:

```verilog
////////////////////////////////////////////////////////////////////////////////
// VectorAdder
////////////////////////////////////////////////////////////////////////////////
module VectorAdder (
        input logic [7:0] in_a,
        input logic [7:0] in_b,
        input logic in_c,
        output logic [7:0] out_r,
        output logic out_c
);

        logic [8:0] full_result;

        assign full_result = in_a + in_b + 9'b0 + in_c;
        assign out_r = full_result[7:0];
        assign out_c = full_result[8];

endmodule
```

> Side-bar: There is one weird thing in here, which is the `+ 9'b0` part. While it is not absolutely necessary in this particular instance, Verilog has some really crazy automatic type-conversion rules that can result in the unexpected truncation of the results. This 'trick' forces the Verilog compiler to create 9-bit results.

# Type determination and propagation

There is something rather unsettling happening here though, if you pay attention. Let's re-write the code to explicit instantiation to bring it to the fore:

```python
class VectorAdder(si.Module):
    in_a = si.Input(si.Unsigned(8))
    in_b = si.Input(si.Unsigned(8))
    in_c = si.Input(si.logic)
    out_r = si.Output(si.Unsigned(8))
    out_c = si.Output(si.logic)

    def body(self):
        full_result = si.Wire(si.Unsigned(9))

        full_result <<= si.sum_gate(self.in_a, self.in_b, self.in_c)
        self.out_r <<= full_result[7:0]
        self.out_c <<= full_result[8]
```

Now, let's assume you want to declare your own `sum_gate` module. How would you go about it?

```python
class sum_gate(Module):
    in_a = si.Input(???)
    ...
```

What would you need to put in as the type of your input_port? Of course you can put in `si.Unsigned(8)`, but that would only work for this particular case.

The answer is in Silicons ability to deduce net-types and propagate them through the design. This facility is not infallible, there are cases when you have to help it along (we'll see that later on) but for the vast majority of uses, it 'just works'.

We start by declaring the ports in the following fashion:

```python
class sum_gate(Module):
    in_a = si.Input()
    in_b = si.Input()
    in_c = si.Input()
    out = si.Output()
```

Notice, that we didn't put any type in the construction arguments. This tells Silicon that we don't wish to assign a type to these ports at this point. A sum_gate module can be instantiated nevertheless and its ports bound. When they are bound (rather, the inputs are bound), their type must match the type of the net they are bound to. Remember, we've started by stating that every net must have one and only one type. So if a port is bound to a net it must also have the same type. Silicon will simply assume that any such untyped port will assume the type of the bound net. Easy.

How about the output though? The way this works is that once all inputs have their types assigned, the `body` of the *instance* can be evaluated. During evaluation the same type-assignment process occurs recursively. Eventually we arrive at primitive instances, that know how to figure out their output type from their inputs. They assign types to their output. At this point we can start climbing up the hierarchy propagating the types from these outputs to nets in the encompassing modules. Eventually this process results in the driver of our `sum_gate.out` port to have an assigned type and Silicon can propagate this type to the output port.

The actual process is a bit more involved but follows the same logic. As long as there are no loops in the data-flow graph, the process is going to succeed. If there are loops (think about a counter for example), you have to help it along. In some other edge-cases (involving much more complex types) it falls on its face and you have to give it some hints.

This might sound like a very complex idea, but the end result is very simple: in many many cases, you don't even have to declare types of nets (or wires or ports) and Silicon will figure it out for you. Of course top-level entities need their inputs defined, but even in our example, we can leave out the type information for our outputs:

```python
class VectorAdder(si.Module):
    in_a = si.Input(si.Unsigned(8))
    in_b = si.Input(si.Unsigned(8))
    in_c = si.Input(si.logic)
    out_r = si.Output()
    out_c = si.Output()

    def body(self):
        full_result = si.Wire(si.Unsigned(9))

        full_result <<= self.in_a + self.in_b + self.in_c
        self.out_r <<= full_result[7:0]
        self.out_c <<= full_result[8]
```

# Cheap generics

This concept of type propagation allows for a very powerful design paradigm: in a very real sense, modules with typeless ports are generic modules. They can be used with varying input and output types and - in many cases - they just work. For instance, one can create a simple ALU:

