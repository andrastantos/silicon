#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__),".."))

from typing import *

from silicon import *
from test_utils import *
import inspect

def test_local_gates():
    class and_gate(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a & in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class and_gate1(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a & in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class and_gate2(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a & in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class and_gate3(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a & in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class and_gate4(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a & in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class or_gate(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'Backend') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a | in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class xor_gate(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a ^ in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class xor_gate1(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a ^ in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class xor_gate2(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a ^ in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class full_adder(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        in_c = Input(logic)
        out_a = Output(logic)
        out_c = Output(logic)
        
        def body(self):
            self.out_a = xor_gate1(self.in_a, xor_gate2(self.in_b, self.in_c))
            self.out_c = or_gate(
                and_gate1(self.in_a, self.in_b),
                or_gate(
                    and_gate2(self.in_a, self.in_c),
                    and_gate3(self.in_b, self.in_c)
                )
            )

    class generic_and_gate(GenericModule):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)

        def construct(self, a, b):
            self.a = a
            self.b = b
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("//a = {}, b = {}\n".format(self.a, self.b))
            ret_val += back_end.indent("assign out_a = in_a & in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val


    class top(Module):
        in_1 = Input(logic)
        in_2 = Input(logic)
        in_3 = Input(logic)
        in_4 = Input(logic)
        out_1 = Output(logic)
        out_2 = Output(logic)
        out_3 = Output(logic)
        out_4 = Output(logic)
        out_5 = Output(logic)
        out_6 = Output(logic)

        def body(self):
            A = and_gate()
            B = and_gate()
            A(in_a = B.out_a)
            A.in_b = B.out_a
            c = and_gate(A.out_a, B.out_a) # In-line instantiation of non-generic modules
            d = and_gate()(c, generic_and_gate(3, 42)(A.out_a, B.out_a)) # In-line instantiation of generic modules. Note the first braces that list the generic parameters, and the second one, listing the port bindings
            dd = d
            xxxx = self.in_4
            xxx = xxxx
            yyyy = self.out_1
            tttt = A.in_a
            ttt = tttt
            d.get_parent_module()._impl.name = "D"
            #A.out_a = B.in_a # This style of binding is only allowed inside the module, not outside
            (out_a, outc) = full_adder(self.in_1, self.in_2, self.in_3)
            out_a.get_parent_module()._impl.name = "FA"
            self.out_2 = self.in_4
            self.out_1 = out_a
            self.out_3 = outc
            #self.out_4 = self.out_3 # This is not allowed (though maybe it should be?)
            #r1 = gc.get_referrers(A)
            #print(str(r1))
            self.out_5 = 0
            self.out_6 = const(1)
    
    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_unconnected_submodule():
    class and_gate(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a & in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class top(Module):
        in_1 = Input(logic)
        in_2 = Input(logic)
        out_1 = Output(logic)

        def body(self):
            A = and_gate()

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

def test_old_number():
    class and_gate(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a & in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class or_gate(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a | in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class xor_gate(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        out_a = Output(logic)
        def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
            ret_val = ""
            assert back_end.language == "SystemVerilog"
            ret_val += self.generate_module_header(back_end) + "\n"
            ret_val += back_end.indent("assign out_a = in_a ^ in_b;\n")
            ret_val += "endmodule\n\n\n"
            return ret_val

    class full_adder(Module):
        in_a = Input(logic)
        in_b = Input(logic)
        in_c = Input(logic)
        out_a = Output(logic)
        out_c = Output(logic)
        
        def body(self):
            self.out_a = xor_gate(self.in_a, xor_gate(self.in_b, self.in_c))
            self.out_c = or_gate(
                and_gate(self.in_a, self.in_b),
                or_gate(
                    and_gate(self.in_a, self.in_c),
                    and_gate(self.in_b, self.in_c)
                )
            )

    class top(Module):
        in_a = Input(Unsigned(length=5))
        in_b = Input(Unsigned(length=16))
        in_c = Input(Unsigned(length=16))
        out_num = Output(Unsigned(length=16))
        out_num_b = Output(Signed(length=16))
        out_a = Output(Unsigned(length=1))
        out_b = Output(Number(signed=False, length=11))
        out_c = Output(Number(signed=False, length=3))
        out_d = Output(Number(signed=False, length=11))

        def body(self):
            # Funny thing. This works:
            #   (a, b) = some_multi_output_gate()
            # This also works:
            #   bus = (a, b, c)
            # This stuff doesnt:
            #   (a, b) = (c, d, e)
            # But, this works too, provided all elements are broken out_a:
            #   (a, b) = bus
            # This again, is borken:
            #   (a, bus_a) = bus_b
            # But maybe it's an edge-case enough that it doesn't matter. We at least get a Python error for the broken cases.
            # We can also make a 'concat' and a 'split' module if we really want to to make single-line assignments like that work.
            a0 = self.in_a[0]
            b0 = self.in_b[0]
            c0 = and_gate(a0, b0)
            self.out_num = self.in_b & self.in_c
            self.out_num_b = 31
            self.out_b[0] = c0
            self.out_b[4] = and_gate(self.in_a[3], self.in_a[4])
            self.out_b[3:1] = self.in_a[3:1]
            self.out_b[10:5] = 0
            #self.out_c = [a0, b0, c0]
            # There's a strange artifact in the generation of this code. It outputs:
            #   assign out_d = {{7{1'bX}}, {in_a[4], in_b[0], u1_out}};
            # This is probably not a big deal, but maybe at some point we sohuld optimize away the extra {} braces to improve readability.
            self.out_d[3:0] = (c0, b0, self.in_a[4])
            self.out_d[10:4] = 0

    test.rtl_generation(top, inspect.currentframe().f_code.co_name)

if __name__ == "__main__":
    test_old_number()
    #test_local_gates()
    #test_unconnected_submodule()

"""
import sys

def trace_calls2(frame, event, arg):
    if event != 'return':
        return
    co = frame.f_code
    func_name = co.co_name
    if func_name == 'write':
        # Ignore write() calls from print statements
        return
    line_no = frame.f_lineno
    filename = co.co_filename
    print('Call to %s on line %s of %s' % (func_name, line_no, filename))
    for local_name, local_value in frame.f_locals.items():
        print("local {} = {}".format(local_name, local_value))
    if func_name in TRACE_INTO:
        # Trace into this function
        #return trace_lines
        return
    return

def c(input):
    print('input =', input)
    print('Leaving c()')

def b(arg):
    val = arg * 5
    c(val)
    print('Leaving b()')


def a():
    old_tracer = sys.getprofile()
    print("old tracer: {}".format(old_tracer))
    sys.setprofile(trace_calls2)
    b(2)
    print('Leaving a()')
    sys.setprofile(old_tracer)
    
TRACE_INTO = ['b']

a()

"""


"""
oldtrace = None
try:
    import pydevd
    debugger=pydevd.GetGlobalDebugger()
    if debugger is not None:
        oldtrace = [debugger.trace_dispatch]
except ImportError:
    pass

if oldtrace is None:
    oldtrace = [frame.f_trace]
"""
"""
General notes on (System)Verilog code-gen:

1. We need to figure out_a when a module needs generating.
2. We also need to figure out_a in what order modules need to be generated.

The second question is a bit easier to answer: we need to walk the hierarcy backward, from leafs to root, in level order of the hierarchy DAG.
This ensures that no module will be instantiated in the generated netlist before it's definition has already been generated.

The first question is a bit more complex because of the dynamic nature of the module instances. We don't necessarily want to generate
a new body for every instance, yet we have to generate enough unqiue bodies to cover all the actual variations.
 - If the configuration parameters (passed in to the construction or something) are different
 - if the port-list is different
 - if the port types (to be implemented) are different
 - if the module tells us so (?)
Not only that, but we'll have to keep around somewhere a list of already existing modules and corresponding module-names such that we can
instantiate the appropriate one in the use-sites.

One thing that can be considered is this: what if modules are of a special meta-class, something that supports operator []. That would allow for all descendents (again, classes, not instances) to have the [] operator implemented on them.
This operator would return a class of which a new instance can be created using the () operator.

The idea here would be that the first [] operator would pass in any generics that are simply stored in a newly created (and cached) class. Then, the instance would be of the type of the newly created class, so - as long as caching works properly -
each parametrization would 'magically just work'.

This would take care of the first bullet-point. It would also allow for finally passing through all the constructor paramters to __call__ and get rid of the double ()s on inline instantiation.

The parameter list can be compared and cached again automagically, along with the port types.

Finally there could be a call-back to customize this behavior.
"""
'''
class M:
    def __class_getitem__(self, *args, **kwargs):
        print("__class_getitem__ called with args: {} and kwargs: {}".format(args, kwargs))
        # TODO: figure out_a what type to return
        return M

# This is nice, but doesn't allow named arguments. With the dict hack we can sort-of use *either* all named *or* all positional arguments, but it gets rather hacky...
m= M[{'a':8,'b':9,'key':"knife"}]()
#
#m[3,4, key=5, new_key=7]


class A:
    def __set_name__(self, owner, name):
        print(f'Calling class: {owner}\nAttribute name: {name}\n')


class B:
    a = A()
    b = A()
    c = A()
    def __init__(self):
        self.xx = A()

x = A()
xxx = B()
xxx.xx = 4

"""
It appears that ports (that can bind) are much better implemented using __set__, __get__ and __delete__ methods then the current hack inside module. This would also remove a bunch of isinstace checks from module as well.
See https://docs.python.org/3/reference/datamodel.html#invoking-descriptors for details. Here's more info on this: https://stackoverflow.com/questions/3798835/understanding-get-and-set-and-python-descriptors. See example below.

Actually, maybe not: the example only works, because celsius is not an instance-variable but a class-variable. For instance variables, this thing doesn't work, which kills dynamic port creation (that is, all ports are part of the class, thus the type).
"""

class Celsius(object):
    def __init__(self, value=0.0):
        self.value = float(value)
    def __get__(self, instance, owner):
        return self.value
    def __set__(self, instance, value):
        self.value = float(value)


class Temperature(object):
    celsius = Celsius()

temp=Temperature()
temp.celsius #calls celsius.__get__
temp.celsius = 14 # calls celsius.__set__

'''

"""
Notes on types:

We need to support type composition. Something along the lines of containers. A logic vector is really a vector of logic things. A struct is a - well - struct of other things.

It would be nice to re-use as much of the existing 'sequence' support from Python as possible. Since custom sequences are possible, all important operations can be customized. Need:
Details: https://docs.python.org/3/reference/datamodel.html#emulating-container-types
__getitem__  (supports slices as well, if done properly)
__setitem__
__delitem__
__iter__
__reversed__
__contains__
__len__
maybe:
__eq__
__hash__

Now, for usage:

Assigning slices of a vector to an input is done this way:
    sum = add(a, b) // length is auto-assigned by return value
    div_by_4 = not_gate(and_gate(sum[0], sum[1]))
Assigning to temporaries is done this way:
    sum = add(a,b)
    msb = sum[-1]
    lsb = sum[0]
This later requires us to track sinks through to members. It means 'msb' is maybe an 'slice port' that - upon binding to an input - registers the true input as a slice sink. The ugliness here is that the source-sink tracking is done in the port object, yet the slice-ness of the data is tracked in the port type.

We also need a way to declare these variables ahead of time:
    sum = signal(vector(logic, 16)) // or something similar, this is rather convoluted.
    sum = add(a, b) // should assert if sums len or other properties aren't right.

This is needed, because:
    sum = signal(vector(logic, 32))
    sum[0:16] = add(a,b)
is needed.

Now to the question of what 'signal' is?

It almost feels like signal is a very special module, with very wierd input and output port creation syntax. But we still have the previous problem that indexing is a type-related thing, yet we're doing it on the port/signal object. So, it seems we'll have to forward these operations to the type.
However that still leaves the slice source-sink management in limbo. Sources and sinks are really not type-related concepts. What we can do is to attach a type-specific 'blob' to every source/sink in a port, which comes from the type.

The final problem is with these changes the 'single source' idea isn't valid anymore. A single source per blob value might still hold as a constraint, making the source field into a dict...
"""

"""
One of the big problems in the current implementation is that variable (and instance) names are not propagated over to the generated RTL. That's because variable names (object references mostly)
get out_a of scope and disappear by the time we get 'generate' phase. We can't capture these names at creation time, because the assignment operator is not something we can override and the LHS creation/construction
happens before the RHS name gets introduced into the caller namespace.

Now, we might be able to sort-of work arond this by encompassing these in a 'with' block: when the __exit__ method is called on the context manager, maybe those names are still there, so we can - maybe -
walk the locals of the calling context (we do have a traceback passed in to __exit__) and fish out_a any new and unknwon names and record them. Since we're at that point within the creation phase, we could
even potentially divine namespace qualifiers by looking at the call-stack.
"""

"""
Vectors:
============
It's not like it's implemented in that way, but one interesting way of thinking about composition (in liu of a minimal language) is that their composition is done through generic and dynamic concatenate' modules.

So, for example, to create a vector from constituents, could be done using a module that support dynamic port creation:
    vector = concatenate(a, vec_b, c)

Extraction can be done using generics:
    sub_vector = split(1,3)(vector)

This setup has the very interesting impact of not needing sub_ports at all. However, it doesn't support vector-like syntax at all.

With this, strange things can be done as well:
    # piece-wise concatenate:
    concatenator = concatenate()
    concatenator(a)
    concatenator(vec_b)
    concatenator(c)
    vector = concatenator() # or vector = concatenator.out_a

With some work, concatenate's __call__ could also take iterables as arguments, so syntax, like this would work too:
    vector = concatenate((a, vec_b, c))
This is silly, but it's just one step away from auto-instantiating concatenators when an input to a port is an iterable, which allows for things like:
    add((a, b), (c,d))

Split might also get better syntax with Junction supporting __getitem__ and automatically instantiate the appropriate split module. With that, stuff, like this would start working:
    sub_vector = vector[1:3]

Now, what still doesn't work is piece-wise assignment, such as:
    vector[1] = a
    vector[4:8] = vec_b
This is the thing that *really* needs the concept of sub-sources

Structs:
============
Structs can mostly follow a similar framework, but now the equivalent of 'concatenate' would need to be a generic as well:
    class Point(Struct):
        x = Vector(Logic, 16) # This is a type, not 'port-like' thing. So, __init__ will have to do some magic for us
        y = Vector(Logic, 16)

    p = make_struct(Point)(x = bus_a, y = bus_b)
    p2 = Wire(Point) # This is also new: we need to create 'wires', which are really unbound Ports, I think. Or, maybe the 'output' of a 'Wire' generic module - if it's the latter, it needs to be special because
         the return value should still be the output, not the module instance...
The equivalent of accessors could be a split operation:
    x_of_p3 = struct_get("x")(p3)
    y_op_p3 = struct_get("y")(p3)
In fact, this might be rolled into the same 'split' that we've used for vectors

Now, by overriding __getattr__ for ports, we can make the usual accessor syntax work as well:
    x_of_pr = p3.x # Instantiates the above struct_get thingy

Just as above, what's broken is piece-wise assignment:
    p3.x = a

This is - again - something that needs the concept of sub-sources.


Constants:
==========
The easiest way to 
"""