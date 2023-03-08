from typing import Optional, List, Set, Dict, Tuple, Callable, Generator, IO, Union, Iterable, Any, Generator
from .module import Module
from vcd import VCDWriter
from .netlist import Netlist, XNet
from .ordered_set import OrderedSet
from collections import OrderedDict
from .utils import Context, is_junction_base
from .exceptions import SimulationException, SyntaxErrorException
from pathlib import Path

"""
A discrete time simulator for Silicon
"""

"""
We are going to keep around one cached event object for every XNet in the netlist.

This is sort of equivalent to 'nets' or 'wires', though there are significant differences:
    1. These events cross hierarchy boundaries and contain the true source, that is the source that can impart a value change to the wire
    2. A sink can be part of multiple events because - for compound types, its possible that a single sink's value can be influenced by many sources
    3. It is however true that every source can be part of at most one event: the one that it sources
    4. Alias management is a bit tricky as the sinks can be part of many events, so their aliases are not uniquely assigned to any particular event.
       This is going to be problematic for waveform generation, when we'll have to figure out what to dump into the VCD files.
       We also need to come up with fully qualified, unique names for each alias, which sort of exists right now in the bowels of RTL generation,
       but that needs to be abstracted out.
    5. These event objects can then be assigned to each port object

    An alternative way of describing the problem is to generate 'convergence' nodes just for the simulator.
"""

def debug_print(*args, **kwargs):
    #print(*args, **kwargs)
    pass

class SimXNetState(object):
    """
    A state object to be attached to each XNet in the system during simulation.
    """
    def __init__(self, sim_context: 'Simulator.SimulatorContext', parent_xnet: XNet):
        self.listeners: Set[Generator] = set() # All the modules that registered to get call-backs on value-change of this port
        net_type = parent_xnet.get_net_type()
        self.value: Any = net_type.get_unconnected_sim_value() if net_type is not None else None
        self.previous_value: Any = None # Previous value
        self.sim_context: 'Simulator.SimulatorContext' = sim_context
        self.parent_xnet = parent_xnet
        self.vcd_vars = []
        self._last_changed = None
        self._last_changed_delta = None
        self._vcd_value_converter = None
        self.value_validator = net_type.validate_sim_value if net_type is not None else (lambda x, y: x)

    def add_listener(self, listener: Generator) -> None:
        self.listeners.add(listener)

    def is_edge(self) -> bool:
        """
        Returns True if there is a change on the port at the current moment in the simulation.
        """
        ret_val = self._last_changed == self.sim_context.now and self._last_changed_delta == self.sim_context.delta
        return ret_val

    def set_value(self, new_value: Any, now: int, delta: int) -> None:
        #print(f"--- at {self.sim_context.now} {self.parent_xnet.get_diagnostic_name(self.sim_context.netlist)} setting value from {self.previous_value} to {new_value}, last changed at {self._last_changed}")
        #assert self._last_changed != self.sim_context.now, "Combinational loop detected???"

        new_value = self.value_validator(new_value, self.parent_xnet.get_source())
        # We have to be careful here: operator != might not do what we think it should, especially if one of the values is None.
        # It really is the simulation implementation of the != operation, not a simulation value comparison.
        # For complex sim values (Number.NetValue), there's a special method provided to check for value changes.
        # We will revert back to != only if such lookup fails.
        try:
            changed = self.value.is_different(new_value)
        except AttributeError:
            try:
                changed = new_value.is_different(self.value)
            except AttributeError:
                changed = self.value != new_value

        if changed:
            if self._last_changed != now:
                self.previous_value = self.value
            self.value = new_value
            self._last_changed = now
            self._last_changed_delta = delta
            self.record_change(now)

            for listener in self.listeners:
                # Inlining schedule_generator
                #self.sim_context.schedule_generator(listener) # Schedule the action on all the modules that registered to this value change
                self.sim_context.simulator.current_event.add_generator(listener)
            self.listeners.clear()

    def get_last_changed(self) -> Optional[int]:
        return self._last_changed

    def record_change(self, when: int):
        if self._vcd_value_converter is None:
            self._vcd_value_converter = self.parent_xnet.get_net_type().convert_to_vcd_type
        vcd_val = self._vcd_value_converter(self.value)
        writer = self.sim_context.vcd_writer
        for vcd_var in self.vcd_vars:
            writer.change(vcd_var, when, vcd_val)



class Simulator(object):
    @staticmethod
    def _process_yield(generator: Generator, yielded_value: Any, sim_context: 'SimulatorContext', now: int) -> None:
        if isinstance(yielded_value, int):
            next_trigger_time = now + yielded_value
            sim_context.schedule_generator(generator, next_trigger_time)
        else:
            # for speed-up purposes, relax the checks and unroll some code:
            # 1. Instead of checking for exact types, check simply for '_xnet' being an attribute
            # 2. Don't double-check these, once for creating the tuple from a single value, then when iterating the same tuple
            if is_junction_base(yielded_value):
                xnet = sim_context.netlist.get_xnet_for_junction(yielded_value)
                xnet.sim_state.add_listener(generator)
            else:
                try:
                    for port in yielded_value:
                        for member_port in port.get_all_member_junctions(add_self=True):
                            if member_port.is_composite():
                                continue
                            xnet = sim_context.netlist.get_xnet_for_junction(member_port)
                            xnet.sim_state.add_listener(generator)
                except TypeError:
                    raise SimulationException(f"The simulate method can only yield an integer, a Port or a sequence of Port objects. The type of the yielded value is {type(port)}", port)

    class Event(object):
        """
        An object that captures all the XNet value changes and callbacks that need to happen at a certain point in time.

        In the Netlist, we have each module assigned a rank. Every non-combinational module is forced to rank 0.
        This means that events flow from rank 0 down to all other ranks. During this flow, we might schedule
        new events for rank-0 elements, but never for others. By processing events in rank-order we can greatly minimize
        the amount of churn in XNet value updates and make the simulation that much faster.
        """
        def __init__(self, when: int, sim_context: 'SimulatorContext'):
            self.max_rank = len(sim_context.simulator.netlist.rank_list)
            self.value_changes: Dict[XNet, Any] = OrderedDict()
            self.when = when
            self.rank_map = sim_context.simulator.netlist.rank_map

            self.generators = []
            for _ in range(self.max_rank):
                self.generators.append(set())

        def add_generator(self, generator: Generator) -> None:
            module = generator.gi_frame.f_locals['self'] # Limitation: We must have a 'self' in the generator params. Else: KeyError is raised
            module_rank = self.rank_map[module]
            # Disabling assert for perf reasons...
            #assert module_rank == 0 or module.is_combinational()
            self.generators[module_rank].add(generator)

        def add_value_change(self, xnet: XNet, value: Any) -> None:
            self.value_changes[xnet] = value

        def trigger(self, sim_context: 'SimulatorContext', now: int) -> None:
            netlist = sim_context.simulator.netlist
            assert now is not None
            #debug_print(f"========= {now}")

            sim_context.reset_delta()

            for xnet, value in self.value_changes.items():
                xnet.sim_state.set_value(value, now, sim_context.delta)
            self.value_changes = OrderedDict()

            # Sort the generators into two groups: ones that belong to combinational modules and ones that are not.
            # Then, we do the following in a loop:
            # 1. Order combinational generators by their rank in the network
            # 2. Call all the lowest-ranked generators, capturing all their updates and the generators that listen to those updates
            # 3. Execute all updates
            # 4. Sort all listeners into rank-order (or non-combinational listeners to their appropriate container)
            # Exit the loop when no more combinational modules are pending generator-call
            # Now call all remaining generators in the normal way

            while True:
                for current_rank, generators_in_rank in enumerate(self.generators):
                    # When yielding to generators, it's possible that they re-schedule themselves at 0 time.
                    # That would result in them being re-inserted into the same generators[current_rank] set.
                    # As such, we can't clear the set after-the-fact. We have to replace it with an empty set
                    # before entering the for loop below
                    self.generators[current_rank] = set()
                    for generator in generators_in_rank:
                        #debug_print(f"--- CG: {generator.gi_frame.f_locals['self']}")
                        try:
                            sensitivity_list = generator.send(now)
                            Simulator._process_yield(generator, sensitivity_list, sim_context, now)
                        except StopIteration:
                            pass # The generator decided not to yield again: simply don't schedule it
                    # The previous loop re-populated value_changes with new things, so let's apply those changes (which will trigger a bunch of listeners, added to the generators)
                    for xnet, value in self.value_changes.items():
                        xnet.sim_state.set_value(value,now, sim_context.delta+1)
                    self.value_changes = OrderedDict()
                if len(self.generators[0]) == 0:
                    break
                sim_context.inc_delta()
            assert sum(len(p) for p in self.generators) == 0

    class SimulatorContext(object):
        def __init__(self, simulator: 'Simulator', vcd_stream: IO, timescale: str):
            from .utils import FQN_DELIMITER

            self.simulator = simulator
            self.vcd_writer = VCDWriter(vcd_stream, timescale=timescale, scope_sep=FQN_DELIMITER)
            self.netlist = simulator.netlist # Cache the netlist object
            self._last_now = None
            self._delta = 0

        def _setup(self) -> None:
            """
            Second phase initialization of simulator context.
            This is needed because we call 'simulate' functions of modules
            here and so we want 'active_context' to be set up properly
            """
            for xnet in self.simulator.netlist.xnets:
                xnet.sim_state = SimXNetState(self, xnet)

            # Schedule an event to call all 'simulate' methods. This will start the simulation.
            for module in self.simulator.netlist.modules:
                # We extract all generators from the 'simulate' methods and run them to the first yield.
                # This means that:
                # - All xnets have a sim value of None
                # - These generators can schedule value-changes to time 0 or otherwise
                # - Most importantly they return their sensitivity list (or delayed schedule time) so we can
                #   put them on the appropriate xnet sensitivity list or event trigger list.
                if hasattr(module, "simulate"):
                    try:
                        generator = module.simulate(self.simulator)
                    except TypeError:
                        generator = module.simulate()

                    from inspect import isgenerator
                    if isgenerator(generator):
                        try:
                            sensitivity_list = generator.send(None)
                        except StopIteration:
                            continue
                        Simulator._process_yield(generator, sensitivity_list, self, 0)

        def dump_signals(self, signal_pattern: str = ".", add_unnamed_scopes: bool = False) -> None:
            from .utils import FQN_DELIMITER
            from re import compile
            filter = compile(signal_pattern)
            for xnet in self.simulator.netlist.xnets:
                port = xnet.get_source() #if xnet.get_source() is not None else first(xnet._sinks)
                if port is None:
                    continue
                if not port.is_specialized():
                    continue
                for scope in xnet.scoped_names.keys():
                    module_name = scope._impl.get_fully_qualified_name()
                    if not self.netlist.symbol_table[scope._impl.parent].is_auto_symbol(scope) or add_unnamed_scopes:
                        names_in_scope = xnet.get_names(scope)
                        for name in names_in_scope:
                            if filter.match(name):
                                xnet.sim_state.vcd_vars.append(self.vcd_writer.register_var(
                                    scope = module_name,
                                    name = name,
                                    var_type = port.vcd_type,
                                    size = port.get_num_bits()
                                ))

        @property
        def now(self) -> int:
            return self.simulator.now

        @property
        def delta(self) -> int:
            return self._delta

        def inc_delta(self) -> None:
            self._delta += 1

        def reset_delta(self) -> None:
            self._delta = 0

        def schedule_generator(self, generator: Generator, when: Optional[int] = None) -> None:
            """
            Called by Event.trigger (through Simulator._process_yield) to re-schedule generator calls
            """
            if when is None or when == self.simulator.now:
                self.simulator.current_event.add_generator(generator)
            else:
                self.simulator._get_event(when).add_generator(generator)

        def schedule_value_change(self, xnet: XNet, value: Any, when: Optional[int] = None) -> None:
            """
            Called by generators or modules to initiate value changes
            """
            if when is None or when == self.simulator.now:
                self.simulator.current_event.add_value_change(xnet, value)
            else:
                self.simulator._get_event(when).add_value_change(xnet, value)

        def tick(self) -> None:
            #print(f"== SIM: tick at {self.now}")
            self.simulator.current_event = self.simulator.timeline.pop(0)
            assert self.now != self._last_now
            self._last_now = self.now
            now = self.now
            self.simulator.current_event.trigger(self, now)

        def simulate(self, end_time: Optional[int] = None) -> int:
            while len(self.simulator.timeline) > 0 and (end_time is None or self.simulator.now < end_time):
                self.tick()
                if self.vcd_writer is not None:
                    self.vcd_writer.flush()
            return self.now

        def _done(self):
            now = self.now
            for xnet in self.simulator.netlist.xnets:
                try:
                    xnet.record_change(now)
                except:
                    # If we can't record the last change, simply leave it as-is
                    pass
                # It's very annoying that simulation asserts clear up the simulation state before raising the exception. So for now, keep it around
                #xnet.sim_state = None
            if self.vcd_writer is not None:
                self.vcd_writer.close()



    def __init__(self, netlist: Netlist, vcd_file: Union[IO,str], timescale='1ns'):
        self.timeline: List['Simulator.Event'] = []
        self.current_event: Optional[Simulator.Event] = None

        self.vcd_file = vcd_file
        self.timescale = timescale
        self.context = None
        self.top_level = netlist.top_level
        self.netlist = netlist

    def __enter__(self):
        assert self.context is None
        assert self.top_level._impl.netlist.simulator_context is None, "Can't start multiple simulations on a single netlist"
        if isinstance(self.vcd_file, (str, Path)):
            self.vcd_stream = open(str(self.vcd_file), "w")
        else:
            self.vcd_stream = self.vcd_file
        self.context = Simulator.SimulatorContext(self, self.vcd_stream, self.timescale)
        self.top_level._impl.netlist.simulator_context = self.context
        Context.push(Context.simulation)
        # We put the top module back to the Module.Context stack as well. That way, anyone knows what the top level is and can query it.
        # This is particularly important to get to the active context (simulation that is) in cases where we have no idea, where in the
        # hierarchy we sit.
        self.module_context = Module.Context(self.top_level._impl)
        self.module_context.__enter__()

        self.current_event = self._get_event(0)
        self.context._setup()
        return self.context

    def __exit__(self, exception_type, exception_value, traceback):
        self.context._done()
        self.context = None
        self.top_level._impl.netlist.simulator_context = None
        self.module_context.__exit__(exception_type, exception_value, traceback)
        self.module_context = None
        old_context = Context.pop()
        assert old_context == Context.simulation
        self.current_event = None

    #TODO: test if we can safely enter and exit a simulator multiple times

    @property
    def now(self) -> int:
        if self.current_event is None:
            return 0
        return self.current_event.when

    @property
    def delta(self) -> int:
        return self.context.delta

    def _get_event(self, when: Optional[int] = None) -> 'Simulator.Event':
        if when is None:
            when = self.now
        insert_idx = len(self.timeline)
        # TODO: since it's an ordered list, bisection could be used for an O(log(n)) complexity search
        for idx, entry in enumerate(self.timeline):
            if entry.when == when:
                return entry
            if entry.when > when:
                insert_idx = idx
                break
        # The exact time doesn't exist in the timeline yet, create a new entry...
        ret_val = Simulator.Event(when, self.context)
        self.timeline.insert(insert_idx, ret_val)
        return ret_val

    def log(self, *args, **kwargs):
        prefix = f"{self.now}:{self.delta}"
        print(f"{prefix:>7} ", end="")
        print(*args, **kwargs)

    def sim_assert(self, condition, *args, **kwargs):
        if not condition:
            prefix = f"{self.now}:{self.delta}"
            print(f"{prefix:>7} ASSERT FAILED ", end="")
            from io import StringIO
            msg = StringIO()
            print(*args, **kwargs, file=msg)
            print(msg)
            raise SimulationException(msg)



    """
    ================================= preparation =================================
    Step 0:
        We need to elaborate (call bodies) to generate and *freeze* the netlist
    Step 1:
        Identify and allocate simulator state for all ports
    Step 2:
        For each port, look at the 'inner_aliases' and 'outer_aliases' and generate FQNs for them. This could be as simple as:
        - Making them unique within the hierarchy
        - Prepend the hierarchy FQN to them
    Step 3:
        Walk the netlist from sink to source and build notification lists.
        These lists will splinter on sub-sources, but should keep snow-balling, until they reach a terminal source, that is one with no sink.
        This terminal source will have the notification list of all ports that in some shape or form sink the value attached to it
        During this walk, we can also build a list of the terminal sources.
        Also during this walk, link up all non-terminal ports with their terminal sources, so their 'value' can be easily obtained from the terminal ports.
    Step 4:
        Set initial value on at minimum all terminal sources. This would normally have the impact of having an event scheduled for all terminal ports for a state-change.
        This event scheduling is probably not what we need, so it needs to be squashed
    Step 5:
        For all 'things' that registered an autonomous trigger (these would be all the 'initial' blocks in Verilog), call them. This would result in the first population
        of signal-change events pushed into the timeline (such as reset going active, maybe other initial values). It would also result in the first in-the-future
        events to be pushed into the timeline for all the 'yield' calls. This is how for example clocks would get generated
    ================================= SIMULATION LOOP =================================
    Simulation has two main steps: signal propagation and action activation
    Step 1:
        Take all the events off of the first entry of the timeline. This action updates 'now' as well, if it changes.
    Step 2:
        Look through all the events and call all their 'trigger' method.
        a. For 'GeneratorEvent's this will cause their associated 'yields' being called, that is all expired yields will be called back.
           This action will result in either more PortValueChangeEvents or more GeneratorEvents being put into the timeline.
        b. For 'PortValueChangeEvents', this will cause their associated terminal sources to assume their new value and all the 'sensitive' modules being
           put into the current_action_collector set.
        c. For 'ModuleActionEvents', this will cause the associated modules' 'simulate' method being called.
           This in turn will (potentially) result in a bunch of new 'PortValueChangeEvent's being pushed into the timeline.
    Step 3:
        If there are any new actions (current_action_collector is not empty), schedule that event to the next delta. This is to say that
        PortValueChange events cause a ModuleActionEvent in the next delta time-step.
    PROBLEMS:
        point 2b and 2c nicely ping-pong between them, which is what you want to present a consistent view of the world. However point 2a can ruin that:
        generator events, if ever get mixed up with PortValueChangeEvents in the same time-step, they will generate off-beat port value changes and consequently
        off-beat module updates.
        The solution to that is that, during the call-back to yields (next() calls) we don't register the next event immediately, instead, we throw it in the current_action_collector.
        That guarantees that test-bench actions and module actions happen in the same beat.
    """
