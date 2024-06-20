from typing import List, Dict, Optional, Sequence
from .module import GenericModule, Module,has_port
from .port import JunctionBase, Input, Output, Wire, Port
from .net_type import NetType
from .auto_input import ClkPort, RstPort
from .primitives import Select, Reg, SelectFirst
from .exceptions import SyntaxErrorException, InvalidPortError
from .rv_interface import ReadyValid
from .rv_buffers import Fifo
from .number import Number, logic, Unsigned
from .composite import GenericMember
from collections import OrderedDict
from dataclasses import dataclass
from .sim_asserts import AssertOnPosClk
from .utils import ScopedAttr
from .arbiters import FixedPriorityArbiter, StickyFixedPriorityArbiter, RoundRobinArbiter, ArbiterGrantEncoding

"""
A rather generic arbiter.

For now, it's a fixed priority arbiter, where arbitration order is given
in the 'arbitration_order' member variable. This is a list of strings, which
are the port prefixes in decreasing priority (i.e. first element is the highest
priority).
"""

class GenericRVArbiter(GenericModule):
    clk = ClkPort()
    rst = RstPort()

    @dataclass
    class PortDesc(object):
        req: JunctionBase
        rsp: JunctionBase
        priority: int = None

    class ClientDesc(object):
        def __init__(self, parent: 'GenericRVArbiter', base_name, priority):
            self.base_name = base_name
            self.priority = priority
            self.parent = parent
            # Create the ports (through calling create_named_port_callback eventually)
            self.request = getattr(parent, f"{base_name}_request")
            self.response = getattr(parent, f"{base_name}_response")



    output_request = Output()
    output_response = Input()
    grant = Output()

    def construct(self, request_if, response_if, max_oustanding_responses, arbitration_algorithm):
        self.request_if = request_if
        self.response_if = response_if
        # See if response port supports back-pressure
        self.response_has_back_pressure = "ready" in self.response_if.get_members()
        self.arbitration_algorithm = arbitration_algorithm

        self.output_request.set_net_type(self.request_if)
        self.output_response.set_net_type(self.response_if)
        self.max_oustanding_responses = max_oustanding_responses
        self.in_get_client = False

        # Request/response ports are dynamically created using the 'get_client'
        # method below. That in turn will create a 'client' class that will
        # contain a reference to the appropriate '_request' and '_response' ports.
        self.clients: Dict[str, 'GenericRVArbiter.ClientDesc'] = OrderedDict()

    def get_client(self, base_name, priority):
        if base_name == "output":
            raise SyntaxErrorException(f"Can't create client port named 'output'. That is a reserved name.")
        with ScopedAttr(self, "in_get_client", True):
            if base_name in self.clients:
                client = self.clients[base_name]
                if priority != client.priority and priority is not None:
                    raise SyntaxErrorException(f"Client {base_name} already has a different priority assigned to it")
                if client.priority is None:
                    client.priority = priority
                return client
            client = GenericRVArbiter.ClientDesc(self, base_name, priority)
            self.clients[base_name] = client
            return client

    def create_named_port_callback(self, name: str, net_type: Optional[NetType] = None) -> Optional[Port]:
        """
        Called from the framework when unknown ports are accessed. This allows for dynamic port creation, though the default is to do nothing.
        Port creation should be as restrictive as possible and for any non-supported name, return None.
        This allows for regular attribute creation for non-port attributes.
        NOTE: create_named_port_callback should return the created port object instead of directly adding it to self
        """
        if not self.in_get_client:
            raise InvalidPortError()

        if name.endswith("_request"):
            if net_type is not None and net_type is not self.request_if:
                raise SyntaxErrorException("Net type '{net_type}' is not valid for port '{name}'")
            port = Input(self.request_if)
            return port
        if name.endswith("_response"):
            if net_type is not None and net_type is not self.response_if:
                raise SyntaxErrorException("Net type '{net_type}' is not valid for port '{name}'")
            port = Output(self.response_if)
            return port

        raise InvalidPortError()

    def body(self):
        for client in self.clients.values():
            if client.priority is None:
                raise SyntaxErrorException(f"Client {client.base_name} has no priority assigned to it")

        ordered_clients = sorted(self.clients.values(), key=lambda x: x.priority, reverse=False)
        arbitration_order = [client.base_name for client in ordered_clients]

        SelectorType = Number(min_val=0, max_val=len(self.clients)-1)
        SelectorFifoIf = type(f"SelectorFifoIf_{self.max_oustanding_responses}", (ReadyValid,), {})
        SelectorFifoIf.add_member("data", SelectorType)

        # Create a FIFO for the replies
        selector_fifo_output = Wire(SelectorFifoIf)
        selector_fifo_input = Wire(SelectorFifoIf)
        selector_fifo_output <<= Fifo(depth=self.max_oustanding_responses)(selector_fifo_input)

        response_port = Wire(SelectorType)

        binary_requestors = Wire(Unsigned(len(self.clients)))
        binary_requestor_indices = {}
        for idx, (name, client) in enumerate(self.clients.items()):
            binary_requestors[idx] <<= client.request.valid
            binary_requestor_indices[name] = idx
        # It seems there should be an easier way to create binary_arbitration_order.
        # However, there's no guarantee that priorities are actually compacted by
        # the user; something that the underlying arbiter depends upon. Given that,
        # and the fact that you probably won't have hundreds of hundreds of clients,
        # I think this is sufficient, if clunky for now.
        binary_arbitration_order = []
        for client_name in arbitration_order:
            binary_arbitration_order.append(binary_requestor_indices[client_name])

        arbiter_logic = self.arbitration_algorithm(arbitration_order=binary_arbitration_order, grant_encoding=ArbiterGrantEncoding.binary)
        selected_port = arbiter_logic(binary_requestors)
        self.grant <<= selected_port

        request_progress = self.output_request.ready & self.output_request.valid & selector_fifo_input.ready
        response_progress = self.output_response.ready & self.output_response.valid if self.response_has_back_pressure else self.output_response.valid

        if has_port(arbiter_logic, "advance"):
            arbiter_logic.advance <<= request_progress

        selector_fifo_input.data <<= selected_port
        response_port <<= selector_fifo_output.data
        selector_fifo_output.ready <<= response_progress

        # Create request mux
        req_selectors = OrderedDict() # Contains a lists for each member
        req_distributors = OrderedDict() # Same for reversed members
        for output_member in self.output_request.get_all_member_junctions(add_self=False, reversed=False): req_selectors[output_member] = []
        for output_member in self.output_request.get_all_member_junctions(add_self=False, reversed=True): req_distributors[output_member] = []

        req_ready_port = self.output_request.ready
        req_valid_port = self.output_request.valid
        for client in self.clients.values():
            req_port = client.request
            for req_selector, member in zip(req_selectors.values(), req_port.get_all_member_junctions(add_self=False, reversed=False)):
                req_selector.append(member)

            for req_distributor, member in zip(req_distributors.values(), req_port.get_all_member_junctions(add_self=False, reversed=True)):
                req_distributor.append(member)

        for output_member, req_selector in req_selectors.items():
            if output_member is req_valid_port:
                output_member <<= Select(selected_port, *req_selector) & selector_fifo_input.ready
                selector_fifo_input.valid <<= Select(selected_port, *req_selector) & self.output_request.ready
            else:
                output_member <<= Select(selected_port, *req_selector)

        for output_member, req_distributor in req_distributors.items():
            if output_member is req_ready_port:
                for idx, req_wire in enumerate(req_distributor):
                    req_wire <<= Select(selected_port == idx, 0, output_member & selector_fifo_input.ready)
            else:
                for idx, req_wire in enumerate(req_distributor):
                    req_wire <<= Select(selected_port == idx, 0, output_member)

        # Create response mux
        # NOTE: This *IS* a reference to the wire object. We will use it later
        #       to find the one reveresed port that needs a 'Select' statement.
        #       All others are just pass-through
        rsp_valid_port = self.output_response.valid
        rsp_distributors = OrderedDict() # Contains a list of lists for each member
        rsp_selectors = OrderedDict() # Same for reversed members
        for output_member in self.output_response.get_all_member_junctions(add_self=False, reversed=False): rsp_distributors[output_member] = []
        for output_member in self.output_response.get_all_member_junctions(add_self=False, reversed=True): rsp_selectors[output_member] = []

        for client in self.clients.values():
            rsp_port = client.response
            for rsp_distributor, member in zip(rsp_distributors.values(), rsp_port.get_all_member_junctions(add_self=False, reversed=False)):
                rsp_distributor.append(member)

            for rsp_selector, member in zip(rsp_selectors.values(), rsp_port.get_all_member_junctions(add_self=False, reversed=True)):
                rsp_selector.append(member)

        for output_member, rsp_distributor in rsp_distributors.items():
            for idx, rsp_wire in enumerate(rsp_distributor):
                if output_member is rsp_valid_port:
                    rsp_wire <<= Select((response_port == idx) & selector_fifo_output.valid, 0, output_member)
                else:
                    rsp_wire <<= output_member

        for output_member, rsp_selector in rsp_selectors.items():
            output_member <<= Select(response_port, *rsp_selector)

        # Make sure the response fifo is never empty if we do get a response
        AssertOnPosClk(selector_fifo_output.valid | ~self.output_response.valid, "Response FIFO is empty while response is received")

class FixedPriorityRVArbiter(GenericRVArbiter):
    def construct(self, request_if, response_if, max_oustanding_responses):
        return super().construct(request_if, response_if, max_oustanding_responses, FixedPriorityArbiter)

class SitckyFixedPriorityRVArbiter(GenericRVArbiter):
    def construct(self, request_if, response_if, max_oustanding_responses):
        return super().construct(request_if, response_if, max_oustanding_responses, StickyFixedPriorityArbiter)

class RoundRobinRVArbiter(GenericRVArbiter):
    def construct(self, request_if, response_if, max_oustanding_responses):
        return super().construct(request_if, response_if, max_oustanding_responses, RoundRobinArbiter)
