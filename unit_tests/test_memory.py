#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__),".."))

from typing import *

from silicon import *
from test_utils import *

import inspect

def test_single_port_ram_no_ports(mode: str = "rtl"):
    config = MemoryConfig(
        MemoryPortConfig(
            addr_type = Unsigned(8),
            data_type = Unsigned(8),
            registered_addr = True,
            registered_data_in = True,
            registered_data_out = False
        ),
        None,
        reset_content = None
    )

    if mode == "rtl":
        with ExpectError(SyntaxErrorException):
            test.rtl_generation(Memory(config), inspect.currentframe().f_code.co_name)

def test_single_port_ram(mode: str = "rtl"):

    class Top(Module):
        data_in = Input(Unsigned(8))
        data_out = Output(Unsigned(8))
        addr = Input(Unsigned(8))
        write_en = Input(logic)
        clk = Input(logic)

        def body(self):
            config = MemoryConfig(
                MemoryPortConfig(
                    addr_type = self.addr.get_net_type(),
                    data_type = self.data_in.get_net_type(),
                    registered_addr = True,
                    registered_data_in = True,
                    registered_data_out = False
                ),
                None,
                reset_content = None
            )
            mem = Memory(config)
            mem.data_in <<= self.data_in
            self.data_out <<= mem.data_out
            mem.addr <<= self.addr
            mem.write_en = self.write_en

    if mode == "rtl":
        test.rtl_generation(Top(), inspect.currentframe().f_code.co_name)

# TODO:
# - Test all 8 combinations of registered in/out
# - Test various address and data-types (structs for example)
# - Test dual-port memories
# - Test simulation

if __name__ == "__main__":
    test_single_port_ram("rtl")
