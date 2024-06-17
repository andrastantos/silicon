from .composite import Interface, Reverse, Struct, is_reverse
from .number import logic
from typing import Union, Callable, Optional
from types import MethodType
from .net_type import NetType
from .port import Junction, Input, Output, Wire, EdgeType
from .auto_input import ClkPort, RstPort
from .module import GenericModule
from .exceptions import SyntaxErrorException
from .utils import TSimEvent, is_iterable
from random import randint

class ReadyValid(Interface):
    ready = Reverse(logic)
    valid = logic

    class Behaviors(Interface.Behaviors):
        def get_data_members(self) -> Junction:
            output_type = self.get_data_member_type()
            ret_val = Wire(output_type)
            for name, (junction, _) in self.get_member_junctions().items():
                if name not in ("ready", "valid"):
                    output_wire = getattr(ret_val, name)
                    output_wire <<= junction
            return ret_val

        def set_data_members(self, data_members: Junction):
            # This doesn't usually work: the caching of get_data_member_type() is per instance, so the comparison almost always fails.
            # TODO: how to make the test easier? The code below will blow up if names are not right, but still
            #if data_members.get_net_type() is not self.get_net_type().get_data_member_type():
            #    raise SyntaxErrorException(f"set_data_members of ReadyValid must be called with a struct of type {self.get_net_type().get_data_member_type()}")
            if not data_members.is_specialized():
                raise SyntaxErrorException("FIXME: This is a limitation of Silicon, but you can't set data-members from a junction which is not specialized")
            for name, (junction, _) in data_members.get_member_junctions().items():
                my_wire = getattr(self, name)
                my_wire <<= junction

    def __init_subclass__(cls):
        cls._init_members()
        # We'll make sure that the subclass doesn't try to reinitialize it's members
        # Sub-classing an interface *will* happen when ports are created.
        def fake_init(cls):
            pass
        cls.__init_subclass__ = MethodType(fake_init, cls)
        # We'll mark the class 'derived' so that add_member will work.
        cls._data_member_type = None

    @classmethod
    def _get_data_member_type(cls) -> Struct:
        try:
            if cls._data_member_type is not None:
                return cls._data_member_type
        except AttributeError:
            raise SyntaxErrorException("To use ReadyValid interfaces, you must create a subclass of ReadyValid")
        cls._data_member_type = type(f"{cls.__name__}.DataMemberStruct", (Struct,), {})
        for name, (member, _) in cls.members.items():
            if name not in ("ready", "valid"):
                cls._data_member_type.add_member(name, member)
        return cls._data_member_type

    def get_data_member_type(self) -> Struct:
        return self.get_net_type()._get_data_member_type()

    @classmethod
    def add_member(cls, name: str, member: Union[NetType, Reverse]) -> None:
        if hasattr(cls, "_data_member_type") and cls._data_member_type is not None:
            raise SyntaxErrorException(f"ReadyValid interface {cls.__name__} doesn't support member addition after data member type is created")
        if is_reverse(member) and name != "ready":
            raise SyntaxErrorException(f"ReadyValid interface {cls.__name__} doesn't support reverse members")
        super().add_member(name, member)

class RvSimSource(GenericModule):
    output_port = Output()
    clock_port = ClkPort()
    reset_port = RstPort()

    class RetryLater(Exception): pass

    def construct(self, data_type: NetType = None, generator: Optional[Callable] = None, max_wait_state: int = 5) -> None:
        if data_type is not None:
            self.output_port.set_net_type(data_type)
        if generator is not None:
            self.generator = generator
        self.max_wait_state = max_wait_state

    def body(self) -> None:
        self.data_members = Wire(self.output_port.get_data_member_type())
        self.output_port.set_data_members(self.data_members)

    def simulate(self, simulator) -> TSimEvent:
        def set_data(next_val):
            if next_val is not None and not is_iterable(next_val):
                try:
                    next_val_net_type = next_val.get_net_type()
                except AttributeError:
                    # We get here if next_val doesn't have 'get_net_type()'
                    next_val_net_type = None
                except TypeError:
                    # We get here if next_val.get_net_type is not callable
                    next_val_net_type = None
                if next_val_net_type is self.data_members.get_net_type():
                    self.data_members <<= next_val
                else:
                    self.data_members <<= (next_val, )
            else:
                # Get here for None or iterables
                self.data_members <<= next_val

        def reset():
            self.output_port.valid <<= 0
            self.wait_state = randint(1,self.max_wait_state+1)
            set_data(self.generator(True, simulator))

        reset()
        while True:
            yield (self.clock_port, )
            edge_type = self.clock_port.get_sim_edge()
            if edge_type == EdgeType.Positive:
                if self.reset_port.sim_value == 1:
                    reset()
                else:
                    if self.wait_state == 0 and self.output_port.ready.sim_value == 1:
                        self.wait_state = randint(1,self.max_wait_state+1)
                    if self.wait_state != 0:
                        self.wait_state -= 1
                        if self.wait_state == 0:
                            try:
                                set_data(self.generator(False, simulator))
                            except RvSimSource.RetryLater:
                                self.wait_state = randint(1,self.max_wait_state+1)
                    self.output_port.valid <<= 1 if self.wait_state == 0 else 0


class RvSimSink(GenericModule):
    input_port = Input()
    clock_port = ClkPort()
    reset_port = RstPort()

    def construct(self, checker: Optional[Callable] = None, max_wait_state: int = 5) -> None:
        if checker is not None:
            self.checker = checker
        self.max_wait_state = max_wait_state

    def body(self) -> None:
        self.data_members = Wire(self.input_port.get_data_member_type())
        self.data_members <<= self.input_port.get_data_members()

    def simulate(self, simulator) -> TSimEvent:
        def reset():
            self.input_port.ready <<= 0
            self.wait_state = randint(1,self.max_wait_state+1)

        reset()
        while True:
            yield (self.clock_port, )
            edge_type = self.clock_port.get_sim_edge()
            if edge_type == EdgeType.Positive:
                if self.reset_port.sim_value == 1:
                    reset()
                else:
                    if self.wait_state == 0 and self.input_port.valid.sim_value == 1:
                        self.wait_state = randint(1,self.max_wait_state+1)
                        sim_val = self.data_members.sim_value
                        #if is_iterable(sim_val) and len(sim_val) == 1:
                        #    sim_val = sim_val[0]
                        self.checker(sim_val, simulator)
                    if self.wait_state != 0:
                        self.wait_state -= 1
                    self.input_port.ready <<= 1 if self.wait_state == 0 else 0

"""
It feels like there should be a way to create a generic state-machine for ready-valid
handshaking that abstracts away *why* data can be consumed or produced by the datapath
and only deals with the ready/valid signalling.

Especially since it's such a PITA to debug those control FSM issues every single time.
But, I can't figure out a good abstraction at the moment.

class RvController(GenericModule):
    input_port = Input()
    output_port = Output()

    input_data = Output()
    output_data = Input()

    can_consume_data = Input(logic)
    do_consume_data = Output(logic)
    producing_data = Input(logic)
    data_consumed = Output(logic)

    clock_port = ClkPort()
    reset_port = RstPort()

    def construct(self, output_interface_type: NetType = None) -> None:
        if output_interface_type is not None:
            self.output_port.set_net_type(output_interface_type)
        else:
            for name, member in self.output_data.get_members():
                self.output_port.add_member(name, member)

        self.input_data.set_net_type(self.input_port.get_data_member_type())

    def body(self) -> None:
        self.input_data <<= self.input_port.get_data_members()
        self.output_port.set_data_members(self.output_data)

        self.input_port.ready <<= self.can_consume_data & self.producing_data
        self.output_port.valid <<= self.producing_data

        self.do_consume_data
"""