# The simulator

The simulator uses `Event` objects to describe what's going to happen at a given point in time. There are two things that can happen:
- A continuation is needed to a `simulate` method
- A value change is needed on an XNet

An `Event` object collects a list of both of these kind of events. When its time to advance the simulated time, the next `Event` object is plucked from the `timeline` and made the `current_event`. Then, it's `trigger` method is called.

## The `Event.trigger` method
This method updates all the required XNet values. This is done through `SimXNetState.set_value`. If there were any objects on the XNets sensitivity list, those are now triggered, and they are added to `current_event`s generator list.

Notice, how the act of updating the values of XNets potentially changes the `Events` generator list.

After all value updates are done, it's time to process the generators. The generators are ranked into 'logic cones' and are executed
in dependency order. Executing a generator means `send`-ing them a signal, which continues their execution from the last `yield` call and up until the subsequent one. During this process, new, updated values are most likely assigned to XNets. These value changes are dully recorded in `current_event`. After each rank of generators is called, another round of value-update is done.

The trick here is this: since these modules are ranked by dependency order, they are guaranteed to generate events for objects further down the rank. By processing the value updates after each rank makes sure that one sweep through the events executes all updates for all logic cones.

Of course, it's possible that some rank-0 (non-combinational) modules were on the sensitivity list of some value updates. In that case, we do need to go through another time and update everybody.

Still, this separation of modules into combinational and otherwise groups greatly improves simulation speed.

But how does Silicon know if a module is combinational? It's an honor system and is based on self-declaration: if the modules `is_combinational` method returns `True`, it's treated as a combinational module. What about modules that instantiate only combinational sub-modules? Are they not combinational then? They are not, technically, but it doesn't really matter. The simulator doesn't actually have to deal with non-primitive modules: their `body` defines a netlist, but it's the netlist that matters. Their `simulate` method is actually empty.
