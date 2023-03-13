from .module import Module
from .port import Input, Output, Wire
from .auto_input import ClkPort, RstPort
from .exceptions import SyntaxErrorException
from .number import logic, Unsigned
from .number import is_number
from .primitives import concat, Reg, Select, SelectFirst

class RoundRobinArbiter(Module):
    from itertools import chain as _chain
    """
    Simple round-robin arbiter.

    - Input is a bit-vector, with each bit corresponding to a requestor.
      The highest order bit has the highest priority.
    - The output is a one-hot encoded bit-vector, where the single set bit
      corresponds to the requestor winning the arbitration.
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
    grants = Output()
    advance = Input(logic)
    restart = Input(logic, default_value = 0)

    def construct(self):
        pass

    def body(self) -> None:
        if not is_number(self.requestors.get_net_type()):
            raise SyntaxErrorException(f"RoundRobinArbiter {self} only supports Numbers as the requestor input type")
        self.grants.set_net_type(self.requestors.get_net_type())

        requestor_cnt = self.requestors.get_num_bits()
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

        masked_requestors = Wire(self.requestors.get_net_type())
        masked_requestors <<= self.requestors & ~concat(mask, "1'b0")
        masked_selector = SelectFirst(
            *(RoundRobinArbiter._chain.from_iterable((req, idx) for req, idx in zip(reversed(masked_requestors), (1<< i for i in range(requestor_cnt-1,-1,-1))))),
            default_port = 0
        )

        unmasked_selector = SelectFirst(
            *(RoundRobinArbiter._chain.from_iterable((req, idx) for req, idx in zip(reversed(self.requestors), (1<< i for i in range(requestor_cnt-1,-1,-1)))))
        )

        self.grants <<= Select(
            masked_selector == 0,
            masked_selector,
            unmasked_selector
        )
