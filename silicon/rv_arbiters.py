from typing import List, Dict, Optional
from .module import GenericModule, Module
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

"""
A rather generic arbiter.

For now, it's a fixed priority arbiter, where arbitration order is given
in the 'arbitration_order' member variable. This is a list of strings, which
are the port prefixes in decreasing priority (i.e. first element is the highest
priority).
"""

class FixedPriorityArbiter(Module):
    requestors = Input()
    selected_requestor = Output()

    # self.arbitration_order contains requestor-indices in descending
    # priority order. So, for instnace, if we had 5 requestors, and
    # self.arbitration_order = (0,4,1,3,2)
    # would mean that self.requestors[0] would be the highest priority,
    # self.requestors[4] would be the next, etc. while self.requestors[2]
    # would have the lowest priority.
    def construct(self):
        self.arbitration_order = None

    def body(self):
        #SelectorType = Number(min_val=0, max_val=self.requestors.get_num_bits())
        #self.selected_requestor.set_net_type(SelectorType)

        selectors = []
        for requestor_idx in self.arbitration_order[:-1]:
            selectors += [self.requestors[requestor_idx], requestor_idx]
        self.selected_requestor <<= SelectFirst(*selectors, default_port = self.arbitration_order[-1])


class RVArbiter(GenericModule):
    clk = ClkPort()
    rst = RstPort()

    arbitration_order: List[str] = []

    @dataclass
    class PortDesc(object):
        req: JunctionBase
        rsp: JunctionBase
        priority: int = None

    # Request/response ports are dynamically created
    # Anything with a '_request' or '_response' ending will be recognized.
    # These ports must be paired up with the same prefix.
    # Of course 'output' is not a valid prefix, or rather it's a different thing
    # altogether.
    ports: Dict[str, PortDesc] = OrderedDict()

    output_request = Output()
    output_response = Input()

    def construct(self, request_if, response_if, max_oustanding_responses):
        self.request_if = request_if
        self.response_if = response_if
        # See if response port supports back-pressure
        self.response_has_back_pressure = "ready" in self.response_if.get_members()

        self.output_request.set_net_type(self.request_if)
        self.output_response.set_net_type(self.response_if)
        self.max_oustanding_responses = max_oustanding_responses

    def create_named_port_callback(self, name: str, net_type: Optional[NetType] = None) -> Optional[Port]:
        """
        Called from the framework when unknown ports are accessed. This allows for dynamic port creation, though the default is to do nothing.
        Port creation should be as restrictive as possible and for any non-supported name, return None.
        This allows for regular attribute creation for non-port attributes.
        NOTE: create_named_port_callback should return the created port object instead of directly adding it to self
        """
        if name.endswith("_request"):
            if net_type is not None and net_type is not self.request_if:
                raise SyntaxErrorException("Net type '{net_type}' is not valid for port '{name}'")
            basename = name[:name.rfind("_request")]
            if basename not in self.ports:
                self.ports[basename] = RVArbiter.PortDesc(None, None)
            port = Input(self.request_if)
            self.ports[basename].req = port
            return port
        if name.endswith("_response"):
            if net_type is not None and net_type is not self.response_if:
                raise SyntaxErrorException("Net type '{net_type}' is not valid for port '{name}'")
            basename = name[:name.rfind("_response")]
            if basename not in self.ports:
                self.ports[basename] = RVArbiter.PortDesc(None, None)
            port = Output(self.response_if)
            self.ports[basename].rsp = port
            return port

        raise InvalidPortError()

    def body(self):

        for name, port_desc in self.ports.items():
            if port_desc.req is None:
                raise SyntaxErrorException(f"RVArbiter port '{name}_requests' is not connected")
            if port_desc.rsp is None:
                raise SyntaxErrorException(f"RVArbiter port '{name}_response' is not connected")

        for idx, name in enumerate(self.arbitration_order):
            if name not in self.ports:
                raise SyntaxErrorException(f"RVArbiter port prefix '{name}' doesn't exist, yet it's listed in 'arbitration_order'")
            self.ports[name].priority = idx

        for name, port_desc in self.ports.items():
            if port_desc.priority is None:
                raise SyntaxErrorException(f"RVArbiter port prefix '{name}' doesn't exist in 'arbitration_order'. Don't know how to build arbiter.")

        SelectorType = Number(min_val=0, max_val=len(self.ports))
        SelectorFifoIf = type(f"SelectorFifoIf_{self.max_oustanding_responses}", (ReadyValid,), {})
        SelectorFifoIf.add_member("data", SelectorType)

        # Create a FIFO for the replies
        selector_fifo_output = Wire(SelectorFifoIf)
        selector_fifo_input = Wire(SelectorFifoIf)
        selector_fifo_output <<= Fifo(depth=self.max_oustanding_responses)(selector_fifo_input)

        response_port = Wire(SelectorType)

        binary_requestors = Wire(Unsigned(len(self.ports)))
        binary_requestor_indices = {}
        for idx, (name, port_desc) in enumerate(self.ports.items()):
            binary_requestors[idx] <<= port_desc.req.valid
            binary_requestor_indices[name] = idx
        binary_arbitration_order = []
        for name in self.arbitration_order:
            binary_arbitration_order.append(binary_requestor_indices[name])

        arbiter_logic = FixedPriorityArbiter()
        arbiter_logic.arbitration_order = binary_arbitration_order
        selected_port = arbiter_logic(binary_requestors)

        #request_progress = self.output_request.ready & self.output_request.valid & selector_fifo_input.ready
        response_progress = self.output_response.ready & self.output_response.valid if self.response_has_back_pressure else self.output_response.valid

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
        for port in self.ports.values():
            req_port = port.req
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

        for port in self.ports.values():
            rsp_port = port.rsp
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


