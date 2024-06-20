from .module import GenericModule
from .port import Input, Output, Wire
from .auto_input import ClkPort, RstPort
from .exceptions import SyntaxErrorException
from .number import logic, Unsigned, Number
from .number import is_number
from .primitives import concat, Reg, Select, SelectFirst
from enum import Enum

class ArbiterGrantEncoding(Enum):
    OneHot = 0
    Binary = 1


class RoundRobinArbiter(GenericModule):

    from itertools import chain as _chain
    """
    Simple round-robin arbiter.

    - Input is a bit-vector, with each bit corresponding to a requestor.
      The highest order bit has the highest priority.
    - The output is either
        - A one-hot encoded bit-vector, where the single set bit
          corresponds to the requestor winning the arbitration.
        - A binary number corresponding to the selected port
    - An additional 'advance' input is used to (on the rising edge of clock)
      advance to the next round-robin scheduling decision
    - Finally a 'restart' input can be used to reset the round-robin decision
      to it's primary state: straight priority selection. This pin is optional.
      If both 'advance' and 'restart' are asserted in the same clock cycle,
      'restart' wins.

    Selection is asynchronous, the only sequential component is the state
    corresponding to the round-robin mask.
    """
    clk = ClkPort()
    rst = RstPort()

    requestors = Input()
    grant = Output()
    advance = Input(logic, default_value = 1)
    restart = Input(logic, default_value = 0)

    # TODO: make arbitration_order functional.
    def construct(self, arbitration_order, grant_encoding: 'ArbiterGrantEncoding' = None):
        if grant_encoding is None: grant_encoding = ArbiterGrantEncoding.Binary
        self.grant_encoding = grant_encoding

    def body(self) -> None:
        requestor_cnt = self.requestors.get_num_bits()

        if not is_number(self.requestors.get_net_type()):
            raise SyntaxErrorException(f"RoundRobinArbiter {self} only supports Numbers as the requestor input type")
        if self.grant_encoding == ArbiterGrantEncoding.OneHot:
            grant_type = self.requestors.get_net_type()
        else:
            grant_type = Number(min_val=0, max_val=requestor_cnt-1)

        self.grant.set_net_type(grant_type)
        mask = Wire(Unsigned(requestor_cnt-1))

        # Mask contains N number of 1's: adding a 1 every type we advance, and resetting to 0, when it's all 1's.
        # This is in essence a shift-register, that always shifts in a 1.
        next_mask = Select(
            mask[0],
            (mask >> 1) | (1 << (requestor_cnt-2)),
            0
        )

        mask <<= Reg(
            Select(
                self.restart,
                Select(
                    self.advance,
                    mask,
                    next_mask
                ),
                0
            )
        )

        # We will have two priority encoders. The first one only looks at inputs that are not masked.
        # If any of these requestors are valid, we use them. If not, (that is to say the bottom N bits are all 0),
        # we use the second (unasked) priority encoder. This encoder will look at all inputs, but
        # (since we know that the bottom N bits are 0) in practice will only select from the top (masked) inputs.

        if self.grant_encoding == ArbiterGrantEncoding.OneHot:
            requestor_values = tuple(1<< i for i in range(requestor_cnt-1,-1,-1))
        else:
            requestor_values = tuple(i for i in range(requestor_cnt-1,-1,-1))

        masked_requestors = Wire(self.requestors.get_net_type())
        masked_requestors <<= self.requestors & ~concat(mask, "1'b0")
        masked_selector = SelectFirst(
            *(RoundRobinArbiter._chain.from_iterable((req, idx) for req, idx in zip(reversed(masked_requestors), requestor_values))),
            default_port = 0
        )
        use_masked_selector = SelectFirst(
            *(RoundRobinArbiter._chain.from_iterable((req, idx) for req, idx in zip(reversed(masked_requestors), (1 for i in range(requestor_cnt-1,-1,-1))))),
            default_port = 0
        )

        unmasked_selector = SelectFirst(
            *(RoundRobinArbiter._chain.from_iterable((req, idx) for req, idx in zip(reversed(self.requestors), requestor_values))),
            default_port = 0
        )

        self.grant <<= Select(
            use_masked_selector,
            unmasked_selector,
            masked_selector
        )

class FixedPriorityArbiter(GenericModule):
    requestors = Input()
    grant = Output()

    # self.arbitration_order contains requestor-indices in descending
    # priority order. So, for instnace, if we had 5 requestors, and
    # self.arbitration_order = (0,4,1,3,2)
    # would mean that self.requestors[0] would be the highest priority,
    # self.requestors[4] would be the next, etc. while self.requestors[2]
    # would have the lowest priority.
    def construct(self, arbitration_order, grant_encoding: 'ArbiterGrantEncoding' = None):
        if grant_encoding is None: grant_encoding = ArbiterGrantEncoding.Binary
        self.arbitration_order = arbitration_order
        self.grant_encoding = grant_encoding

    def body(self):
        #SelectorType = Number(min_val=0, max_val=self.requestors.get_num_bits())
        #self.grant.set_net_type(SelectorType)

        selectors = []
        for requestor_idx in self.arbitration_order[:-1]:
            grant_value = (1 << requestor_idx) if self.grant_encoding == ArbiterGrantEncoding.OneHot else requestor_idx
            selectors += [self.requestors[requestor_idx], grant_value]
        default_grant_value = (1 << self.arbitration_order[-1]) if self.grant_encoding == ArbiterGrantEncoding.OneHot else self.arbitration_order[-1]
        self.grant <<= SelectFirst(*selectors, default_port = default_grant_value)

class StickyFixedPriorityArbiter(GenericModule):
    requestors = Input()
    grant = Output()
    clk = ClkPort()
    rst = RstPort()

    # self.arbitration_order contains requestor-indices in descending
    # priority order. So, for instnace, if we had 5 requestors, and
    # self.arbitration_order = (0,4,1,3,2)
    # would mean that self.requestors[0] would be the highest priority,
    # self.requestors[4] would be the next, etc. while self.requestors[2]
    # would have the lowest priority.
    def construct(self, arbitration_order, grant_encoding: 'ArbiterGrantEncoding' = None):
        if grant_encoding is None: grant_encoding = ArbiterGrantEncoding.Binary
        self.arbitration_order = arbitration_order
        self.grant_encoding = grant_encoding

    def body(self):
        SelectorType = Number(min_val=0, max_val=self.requestors.get_num_bits()-1)

        # We will use the highest priority requestor as the 'nothing is selected'
        # value.
        last_requestor = Wire(SelectorType)

        selectors = []
        for requestor_idx in self.arbitration_order[:-1]:
            grant_value = (1 << requestor_idx) if self.grant_encoding == ArbiterGrantEncoding.OneHot else requestor_idx
            selectors += [self.requestors[requestor_idx], grant_value]
        default_grant_value = (1 << self.arbitration_order[-1]) if self.grant_encoding == ArbiterGrantEncoding.OneHot else self.arbitration_order[-1]
        current_requestor = SelectFirst(*selectors, default_port = default_grant_value)
        sticky_request = Select(last_requestor, *self.requestors) # contains the current request state of the previously selected requestor
        grant = Select(sticky_request, current_requestor, last_requestor) # select the previously selected requestor if it keeps requesting
        last_requestor <<= Reg(grant, reset_value_port=self.arbitration_order[0])
        self.grant <<= grant

