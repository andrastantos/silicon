from typing import List, Dict, Optional
from .module import GenericModule
from .port import JunctionBase, Input, Output, Wire, Port
from .net_type import NetType
from .auto_input import ClkPort, RstPort
from .primitives import Select, Reg, SelectFirst, SRReg
from .exceptions import SyntaxErrorException, InvalidPortError
from .number import Number, logic
from collections import OrderedDict
from dataclasses import dataclass

"""
A rather generic arbiter.

For now, it's a fixed priority arbiter, where arbitration order is given
in the 'arbitration_order' member variable. This is a list of strings, which
are the port prefixes in decreasing priority (i.e. first element is the highest
priority).
"""
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

    def construct(self, request_if, response_if):
        self.request_if = request_if
        self.response_if = response_if
        # See if response port supports back-pressure
        self.response_has_back_pressure = "ready" in self.response_if.get_members()

        self.output_request.set_net_type(self.request_if)
        self.output_response.set_net_type(self.response_if)


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


        selected_port = Wire(Number(min_val=0, max_val=len(self.ports)))

        selectors = []
        for idx, name in enumerate(self.arbitration_order[:-1]):
            port_desc = self.ports[name]
            selectors += [port_desc.req.valid, idx]
        selected_port_comb = SelectFirst(*selectors, default_port = self.ports[self.arbitration_order[-1]].req.valid)

        request_progress = self.output_request.ready & self.output_request.valid
        response_progress = self.output_response.ready & self.output_response.valid if self.response_has_back_pressure else self.output_response.valid

        active = SRReg(request_progress, response_progress)

        selected_port <<= Reg(selected_port_comb, clock_en=request_progress)

        # Create request mux
        req_selectors = OrderedDict() # Contains a lists for each member
        req_distributors = OrderedDict() # Same for reversed members
        for output_member in self.output_request.get_all_member_junctions(add_self=False, reversed=False): req_selectors[output_member] = []
        for output_member in self.output_request.get_all_member_junctions(add_self=False, reversed=True): req_distributors[output_member] = []

        for name in self.arbitration_order:
            req_port = self.ports[name].req
            for req_selector, member in zip(req_selectors.values(), req_port.get_all_member_junctions(add_self=False, reversed=False)):
                req_selector.append(member)

            for req_distributor, member in zip(req_distributors.values(), req_port.get_all_member_junctions(add_self=False, reversed=True)):
                req_distributor.append(member)

        for output_member, req_selector in req_selectors.items():
            output_member <<= Select(selected_port_comb, *req_selector)

        for output_member, req_distributor in req_distributors.items():
            for idx, req_wire in enumerate(req_distributor):
                req_wire <<= Select(selected_port_comb == idx, 0, output_member)

        # Create response mux
        # NOTE: This *IS* a reference to the wire object. We will use it later
        #       to find the one reveresed port that needs a 'Select' statement.
        #       All others are just pass-through
        rsp_valid_port = self.output_response.valid
        rsp_distributors = OrderedDict() # Contains a list of lists for each member
        rsp_selectors = OrderedDict() # Same for reversed members
        for output_member in self.output_response.get_all_member_junctions(add_self=False, reversed=False): rsp_distributors[output_member] = []
        for output_member in self.output_response.get_all_member_junctions(add_self=False, reversed=True): rsp_selectors[output_member] = []

        for name in self.arbitration_order:
            rsp_port = self.ports[name].rsp
            for rsp_distributor, member in zip(rsp_distributors.values(), rsp_port.get_all_member_junctions(add_self=False, reversed=False)):
                rsp_distributor.append(member)

            for rsp_selector, member in zip(rsp_selectors.values(), rsp_port.get_all_member_junctions(add_self=False, reversed=True)):
                rsp_selector.append(member)

        for output_member, rsp_distributor in rsp_distributors.items():
            for idx, rsp_wire in enumerate(rsp_distributor):
                if output_member is rsp_valid_port:
                    rsp_wire <<= Select((selected_port == idx) & active, 0, output_member)
                else:
                    rsp_wire <<= output_member

        for output_member, rsp_selector in rsp_selectors.items():
            output_member <<= Select(selected_port, *rsp_selector)


