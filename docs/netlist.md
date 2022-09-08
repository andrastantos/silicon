# Netlists

`Netlist` is a core concept for Silicon. A `Netlist` instance contains everything there is to know about a Silicon project: all the `Module` instances, and all their connections. It knows about all the `Junction`s, all the `NetType`s within the project as well.

A `Netlist` is created (usually) through a simple `with` construct:

    with Netlist().elaborate() as netlist:
        top = top_class()

This code creates a global `Netlist` instance, that is referenced while creating the top level module. After the top level class is created, the whole netlist is elaborated, that is to say: submodules, and their connectivity is established.

It is important that a global `Netlist` instance exists during elaboration. The reason for this is that there are a lot of built-in methods (`__new__`, `__init__`, `__add__` etc.) getting called during the execution of `body` where we need to know the netlist instance to make the magic work. The `with` block ensures that such a global variable is created and then safely removed.

The reason for the - potentially - strange syntax is to allow maximum flexibility in the way the top module instance is created. A global `Netlist` instance must exist during the construction of this object, but Silicon doesn't restrict the way this object is constructed. You might want to do any of the following things:

- A simple construction of an object, just as shown above
- Create a different top level module instance based on circumstance, for instance whether you want to do RTL generation or simulation (in which case the top-level is your test-bench code).
- Create a generic top level module instance, in which case parameters are passed to the constructor.
- Do more complex things, such as read configuration files, download content for sub-modules, etc.

It is also important to note, that the real work happens when the `with` block exists. Really, only the top level object construction is what is done inside the `with` block. The `body` of the top level module is only called inside the `__exit__` method of the `with` block. That's where all the submodules and their connectivity (recursively) created.

## Elaboration
The elaboration of the netlist has the following phases:

- The execution of the body of a module. This creates a set of sub-modules and their connectivity
- Order remaining sub-modules. Sub-modules are ordered in the order their outputs are accessed. However, some sub-modules might not have an output at all, in which case they remain unordered. They are simply thrown into the end of the ordered list. The purpose of this ordering is to minimize (or at least attempt to minimize) the number of intermediate wires that are needed during RTL generation.
- Slice finalization. **TODO**: this actually should be PHI-node insertion, and I'm not sure where is the right place to do it.
- Finalize auto-input bindings. **TODO**: this should probably happen before PHI-node insertion
- Removal of any local wires that are not part of the netlist (no sinks, no sources)
- In a loop, until all net types are known and all sub-modules are elaborated
  - Net types are propagated
  - If a sub-module has all its inputs specialized, it is recursively elaborated

## Post elaboration
**TODO** This is not the right name for this. All of the above happens within `Module.Impl._elaborate`. There is also `Netlist._elaborate`, that does a bunch more:

- Register all junctions (recursively). This involves:
  - Registering all net-types
  - Registering all port variants (Input, Output, etc.)
- Create XNets (NOTE: XNets don't introduce names into the symbol table)
- Recursively in the sub-module hierarchy:
  - Creating a symbol table
  - Populate sub-module names
  - Populate XNet names
- Fill the names of XNets. That is, collect all the names for all the scopes the XNet spans and populate the relevant XNet object attributes.
- Rank the netlist. This is a flattened operation where only primitives play a role. Anything that's not declared as combinational gets to assigned rank-0, then a logic-cone is created for each of their outputs.
- Finally, we print out the sub-module hierarchy.

## Symbol tables
We have a symbol table for each scope (Module). They are stored in Module.Impl.symbol_table. Symbol tables store names that are used for RTL generation and generally match the names of the objects in the Python code. There can be name-collisions in several scenarios though:
- If several `with` blocks create aliases for different underlying nets.
- Unnamed sub-module (or in some cases wire) instances get assigned an auto-generated name. These can collide.
- When a net gets split due to the insertion of an adaptor (during type propagation) both sides of the split net gets assigned the same name.

Symbol-tables generally map names to objects. They also help in resolve conflicts (maintain a counter for used base-names to support the generation of 'wire1', 'wire2' etc. names) and check for reserved names.

The important thing to note here is that SymbolTables can't make objects to their names. Which is probably wrong and they should. At any rate, that functionality at the moment is in the individual objects themselves, which - again - is probably wrong.

Once that is changed, SymbolTables should become part of Netlist, not Module as it is now and they (it, really at that point) should have the concept of a 'scope'.

This SymbolTable should also exist from the very beginning and be used exclusively for mapping objects to their names. This will become problematic though if objects start their life without names and get assigned names later. Or, maybe not...


*** In the tracer, I should never have to create a naming wire. To be checked, but I think the construction of a wire already registers it as a _local_wire, which is to say, that it should already exist. Always. We should just set it's local_name to whatever we find in the local map.
*** Actually, there can still be a need for a naming wire:

   a = b + c
   d = a

Now, we'll find two local variables (a and d) referencing the same object. So, maybe the current code is not all that bad after all.

**TODO**: we need to maintain the state of the netlist, so that the order of calls can't be changed. Right now we could call generate before elaborate and so on.

## TODO:
Progress: modules are now using the global symbol table for name management. Of course this was the easiest to deal with, Junctions and XNets are going to be more involved. Still, this is progress, among other things, it helped me debug the global SymbolTable object quite a bit.
- populate_submodule_names should not really exist --> we should 'make_unique' the global symbol table
- reserved names should be populated into global symbol table (commented out for easy debugging)

## Names in Junctions

### Wires
Apparently `Wires` are special: they can have a `local_name` and a `rhs_expression`. `local_name` is assigned in `register_local_wire` and in `propagate_net_types`.

We seem to be getting into a problem here: as we create XNets we seem to register *those* in the symbol table, under the name of the original wires, maybe `Junctions` in general. That's not proper behavior, and something that the current global SymbolTable support.

In some ways, it makes sense: an XNet is really the entity we care about: it's the actual 'thing'. `Junctions` are just temporary measures to get to XNets. So, maybe what we should do is once we have a (unique) name for everything, we should have a pass that replaces all junctions with their corresponding XNet in the symbol table.

... and once we've done that XNet.scoped_names should get killed.

### Junctions
`Junctions` also have an `interface_name` attribute.


## Global Symbol Table

For each Module instance, there are actually two scopes (namespace if you wish) created. One, keyed by the Module instance contains all symbols that are accessible inside the module. The other, keyed by a Module.Impl.Interface instance, contains all the interface            port entities with their interface names. Consider the following code:

    class MyModule(Module):
        my_input = Input()
        my_output = Ouptut(logic)

        def body(self):
            self.alias = self.my_input
            local_alias = self.my_output

In the above code, both the input and the output ports have two references and two names. The input can be called both as `my_input` and as `alias` in the inside of the module, while the output can be called `my_output` and `local_alias`. However, `alias` and `local_alias` are not names that are part of the interface. Only `my_input` and `my_output` are.

Here's the problem with this approach: if a single symbol is registered in two different scopes, there's no guarantee that the names remain the same after collision resolution. We are heavily reliant on this resolution to fix auto-generate duplicate symbols. In fact, tracking that is the main reason to have a global symbol table to begin with - most if not all user-generated names are derived from local variables or attributes, and so are more or less unique to begin with.

So, I guess there needs to be a way to add 'locked' entries, which are not fixed.


!!!!!!!!!!!!!!
Modules can have multiple names. Ports can also have multiple names, even multiple explicit names under some special circumstances.
It's probably worth the effort to maintain a reverse-mapping from object to explicit name as well.
We should also check that the same name cannot be in both the implicit and explicit symbol tables.


module.get_interface_name

This needs to change:
                                    if not self.netlist.symbol_table[parent_module._impl.parent].is_auto_symbol(parent_module):
We should use 'scope' here which already exists.

module.set_name: it has an 'explicit' argument. That should be 'hard', if anything at all.
register_local_wire has a similar problem