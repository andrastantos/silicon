# Memories have soooooo many variants, not even counting memory-compilers.
# What we support at the moment:
# MEMORY TYPE
# - ROM
# - RAM
# PORT CONFIGURATION
# - Arbitrary number of ports
# - Read-only ports
# - Write-only ports
# - Read-write ports
# - Independent widths on each port
# READ PORTS
# - 0-cycle latency (asynchronous access)
# - 1-cycle latency (registered data)
# - 2-cycle latency (registered address and data)
# WRITE PORTS
# - Byte-enables (or maybe section-enables?)
# - 0-cycle latency
# - 1-cycle latency (registered address and data)
# READ-WRITE PORTS
# - All of the above, plus:
# - WRITE_FIRST (output data = write data during writes)
# - READ_FIRST (output data = old memory condent during writes)
# - NO_CHANGE (output data = data from last read during writes)
# PORT CONFLICTS (SYNC PORTS)
# - read  while write to same address: results in old memory content
# - read  while write to same address: results in data written (not supported by XILINX or ALTERA)
# - read  while read  to same address: as expected
# - write while write to same address: non-deterministic
# - read  while write to different address: as expected
# - read  while read  to different address: as expected
# - write while write to different address: as expected
# PORT CONFLICTS (ASYNC PORTS)
# - read  while write to same address: non-deterministic
# - read  while read  to same address: as expected
# - write while write to same address: non-deterministic
# - read  while write to different address: as expected
# - read  while read  to different address: as expected
# - write while write to different address: as expected
# ERROR-CORRECTION
# - None
# - Parity
# - ECC (might add extra latency)
# - ECC with auto-correct (needs read-modify-write cycles for failed reads)
# POWER MANAGEMENT (what is the latency of each of these??)
# - None
# - Clock-gating (retention)
# - Power-gating
# CONTENT MANAGEMENT (RAM)
# - Initial content
# - Reset to zero (sync/async)
# - Undefined on power-on
# CONTENT MANAGEMENT (ROM)
# - Initial content
# ALTERA SPECIALTIES:
# - Input and output registers can be independently clocked (that is different clock for read address and read data)
# - Address and data input can be independently registered or not (that is different latency for write address and write data)
# MISC:
# - Async memories (ASICs seem to have it)
# - External memories (let's not go there...)
# - JTAG support (ASIC only)
# - Line replacement (ASIC only)
# - Lots of technology parameters (ASIC only)
#
# Other notes:
# - There's a 'fake' memory generator, called 'OpenRAM' that can be used for experimentation
# - There's another 'fake' memory generator, called CACTI (https://www.hpl.hp.com/research/cacti/) that only generates size/power models but can still be useful potentially.
#
# !!!!! IT APPEARS THAT NOONE SUPPORTS MORE THAN 2 PORTS ON SRAM ARRAYS !!!!
#
# That still leaves out register files, that can have many many ports. It might be worth breaking that application out though.
#
# Memory compiler vendors:
# Synopsys
# ARM (Artisan)
# Essentially 'contact your foundry'

from .module import GenericModule, has_port
from .port import Input, Output, Wire, AutoInput, Port
from .net_type import NetType
from collections import OrderedDict
from dataclasses import dataclass
from .composite import Struct
from .utils import str_block, is_power_of_two
from .exceptions import SyntaxErrorException
from typing import Optional, Sequence
from .number import logic
from .utils import TSimEvent

@dataclass
class MemoryPortConfig:
    addr_type: Optional[NetType] = None
    data_type: Optional[NetType] = None
    registered_input: bool = True
    registered_output: bool = False
    prefix: Optional[str] = None

@dataclass
class MemoryConfig:
    port_configs: Sequence[MemoryPortConfig]
    reset_content: Optional[str] = None

# TODO:
# - Add read-enable port
# - Add reset option for registers
# - Add byte-enables
# NOTE:
# - The current implementation correctly identifies if the various port-clocks are sourced by the same clock source and will generate
#   the appropriate reference to a common clock port name. This is due to the behavior of XNets and the way we look up rhs-name for the clocks.
#   HOWEVER: that means that if we've used the same 'template' in a single-clock and in a dual-clock configuration, we'll have to make sure
#            that they don't compare equal and a different module body is generated (and referenced) for each. It is important to note that
#            there's nothing different between these objects! It's just that they are *used* differently, yet they generate different bodies.

class Memory(GenericModule):
    INPUT = 1
    OUTPUT = 2
    def construct(self, config: MemoryConfig):
        from copy import deepcopy
        self.config = deepcopy(config)
        self.optional_ports = OrderedDict()
        for idx, port_config in enumerate(self.config.port_configs):
            port_prefix = f"port{idx+1}"
            if port_config is not None:
                if port_config.prefix is None:
                    if self.get_port_count() == 1:
                        port_config.prefix = ""
                    else:
                        port_config.prefix = port_prefix + "_"
                else:
                    port_config.prefix += "_"
        for port_config in self.config.port_configs:
            setattr(self, f"{port_config.prefix}addr", Input(port_config.addr_type))
            self.optional_ports[f"{port_config.prefix}data_in"] = (port_config.data_type, Memory.INPUT)
            self.optional_ports[f"{port_config.prefix}data_out"] = (port_config.data_type, Memory.OUTPUT)
            self.optional_ports[f"{port_config.prefix}write_en"] = (logic, Memory.INPUT)
            setattr(self, f"{port_config.prefix}clk", AutoInput(logic, keyword_only = True, auto_port_names = (f"{port_config}_clk", f"{port_config}_clock", "clk", "clock"), optional = False))

    def create_named_port(self, name: str) -> Optional[Port]:
        """
        Called from the framework when unknown ports are accessed. This allows for dynamic port creation, though the default is to do nothing.
        Port creation should be as restrictive as possible and for any non-supported name, return None.
        This allows for regular attribute creation for non-port attributes.
        NOTE: create_named_port should return the created port object instead of directly adding it to self
        """
        if name in self.optional_ports:
            if self.optional_ports[name][1] == Memory.INPUT:
                return Input(self.optional_ports[name][0])
            elif self.optional_ports[name][1] == Memory.OUTPUT:
                return Output(self.optional_ports[name][0])
            else:
                assert False
        return None

    def get_port_count(self) -> int:
        return len(self.config.port_configs)

    def _get_port_ports(self, port_config) -> Sequence[Port]:
        data_in_port = getattr(self, f"{port_config.prefix}data_in", None)
        data_out_port = getattr(self, f"{port_config.prefix}data_out", None)
        write_en_port = getattr(self, f"{port_config.prefix}write_en", None)
        addr_port = getattr(self, f"{port_config.prefix}addr")
        clk_port = getattr(self, f"{port_config.prefix}clk", None)
        return data_in_port, data_out_port, write_en_port, addr_port, clk_port

    def _setup(self):
        self.primary_port_config = None
        self.secondary_port_configs = []

        for port_config in self.config.port_configs:
            data_conf_bits = port_config.data_type.get_num_bits() if port_config.data_type is not None else None
            addr_conf_bits = port_config.addr_type.get_num_bits() if port_config.addr_type is not None else None

            data_in_port, data_out_port, write_en_port, addr_port, clk_port = self._get_port_ports(port_config)

            if data_in_port is None and data_out_port is None:
                raise SyntaxErrorException(f"Memory has neither its read nor its write data connected. That's not a valid use of a memory")
            if data_in_port is None and self.config.reset_content is None:
                raise SyntaxErrorException(f"For ROMs, reset_content must be specified")
            if write_en_port is not None and data_in_port is None:
                raise SyntaxErrorException("If a memory has a write-enable, it must have a corresponding data")
            if not port_config.registered_input and data_in_port is not None:
                raise SyntaxErrorException("Unregistered inputs are only supported for read ports on inferred memories")

            if data_in_port is not None:
                data_in_bits = data_in_port.get_net_type().get_num_bits()
                if data_conf_bits is not None and data_conf_bits < data_in_bits:
                    raise SyntaxErrorException(f"Memory was specified as {data_conf_bits} wide in config, yet data input port is {data_in_bits} wide")
            if data_out_port is not None:
                if not data_out_port.is_abstract():
                    data_out_bits = data_out_port.get_net_type().get_num_bits()
                    if data_conf_bits is not None and data_conf_bits < data_out_bits:
                        raise SyntaxErrorException(f"Memory was specified as {data_conf_bits} wide in config, yet data output port is {data_out_bits} wide")

            if data_conf_bits is not None:
                data_bits = data_conf_bits
            elif data_in_port is not None and data_out_port is not None:
                data_bits = max(data_in_bits, data_out_bits)
            elif data_in_port is not None:
                data_bits = data_in_bits
            elif data_out_port is not None:
                data_bits = data_out_bits
            else:
                assert False, "We should have caught this above"

            addr_bits = addr_port.get_net_type().get_num_bits()
            if addr_conf_bits is not None and addr_bits > addr_conf_bits:
                raise SyntaxErrorException(f"Memory was specified with address width of {addr_conf_bits} in config, yet address input port is {addr_bits} wide")
            if addr_conf_bits is not None:
                addr_bits = max(addr_conf_bits, addr_bits)
            port_config.addr_bits = addr_bits
            port_config.data_bits = data_bits

        # Determine memory size
        self.mem_size = 0
        self.mem_data_bits = 0
        for port_config in self.config.port_configs:
            data_bits = port_config.data_bits
            addr_bits = port_config.addr_bits
            self.mem_size = max(self.mem_size, data_bits * (1 << addr_bits))
            self.mem_data_bits = max(data_bits, self.mem_data_bits)

        # Finding primary and secondary ports, while checking for port compatibility
        for port_config in self.config.port_configs:
            data_bits = port_config.data_bits
            if self.mem_data_bits % data_bits != 0:
                raise SyntaxErrorException(f"For multi-port memories, data sizes on all ports must be integer multiples of one another")
            ratio = self.mem_data_bits // data_bits
            if not is_power_of_two(ratio):
                raise SyntaxErrorException(f"For multi-port memories, data size ratios must be powers of 2")

            port_config.mem_ratio = ratio
            if ratio == 1 and self.primary_port_config is None:
                self.primary_port_config = port_config
            else:
                self.secondary_port_configs.append(port_config)

        # Checking port interactions
        primary_data_in_port, primary_data_out_port, _, _, _ = self._get_port_ports(self.primary_port_config)

        has_data_in = primary_data_in_port is not None
        has_data_out = primary_data_out_port is not None
        for secondary_port_config in self.secondary_port_configs:
            secondary_data_in_port, secondary_data_out_port, _, _, _ = self._get_port_ports(secondary_port_config)
            has_data_in |= secondary_data_in_port is not None
            has_data_out |= secondary_data_out_port is not None

        if not has_data_in and not has_data_out:
            raise SyntaxErrorException(f"Memory has neither its read nor its write data connected. That's not a valid use of a memory")
        if not has_data_in and self.config.reset_content is None:
            raise SyntaxErrorException(f"For ROMs, reset_content must be specified")


    def generate_single_port_memory(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        # Sing-port memory
        prot_config = self.config.port_configs[0]

        data_bits = prot_config.data_bits
        addr_bits = prot_config.addr_bits

        rtl_body =  f"\twire [{data_bits-1}:0] mem [{(1 << addr_bits)-1}:0];\n"

        if self.config.reset_content is not None:
            rtl_body += f"\tinitial begin\n"
            if callable(self.config.reset_content):
                generator = self.config.reset_content(data_bits, addr_bits)
                try:
                    for addr in range(1 << addr_bits):
                        data = next(generator)
                        rtl_body += f"\t\tmem[{addr}] <= {data_bits}'h{data:x};\n"
                except StopIteration:
                    pass # memory content is only partially specified
                generator.close()
            else:
                rtl_body += f'\t\t$readmemb("{self.config.reset_content}", mem);\n'
            rtl_body += f"\tend\n"

        data_in_port, data_out_port, write_en_port, addr_port, clk_port = self._get_port_ports(prot_config)

        # some preparation for inlining...
        target_namespace = self
        data_in, _ = target_namespace._impl.get_rhs_expression_for_junction(data_in_port, back_end) if data_in_port is not None else (None, None)
        data_out = target_namespace._impl.get_lhs_name_for_junction(data_out_port) if data_out_port is not None else None
        write_en, _ = target_namespace._impl.get_rhs_expression_for_junction(write_en_port, back_end) if write_en_port is not None else (None, None)
        addr, _ = target_namespace._impl.get_rhs_expression_for_junction(addr_port, back_end) if addr_port is not None else (None, None)
        clk, _ = target_namespace._impl.get_rhs_expression_for_junction(clk_port, back_end, back_end.get_operator_precedence("()")) if clk_port is not None else (None, None)

        if data_out_port is not None:
            if prot_config.registered_input:
                rtl_body += f"\twire [{addr_bits-1}:0] addr_reg;\n"
                addr_name = "addr_reg"
            else:
                addr_name = addr
        if data_in_port is not None or (data_out_port is not None and prot_config.registered_input):
            rtl_body += f"\talways @(posedge {clk}) begin\n"
            if data_in_port is not None:
                if write_en_port is not None:
                    rtl_body += f"\t\tif ({write_en}) begin\n"
                    rtl_body += f"\t\t\tmem[{addr}] <= {data_in};\n"
                    rtl_body += f"\t\tend\n"
                else:
                    rtl_body += f"\t\tmem[{addr}] <= {data_in};\n"
            if data_out_port is not None and prot_config.registered_input:
                rtl_body += f"\t\t{addr_name} <= {addr};\n"
            if data_out_port is not None and prot_config.registered_output:
                rtl_body += f"\t\t{data_out} <= mem[{addr_name}];\n"
            rtl_body += f"\tend\n"
        if data_out_port is not None and not prot_config.registered_output:
            rtl_body += f"\t{data_out} <= mem[{addr_name}];\n"
        return rtl_body

    def generate_dual_port_memory(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        mem_addr_range = self.mem_size // self.mem_data_bits

        # some preparation for inlining...
        target_namespace = self

        rtl_body = ""

        primary_data_in_port, primary_data_out_port, primary_write_en_port, primary_addr_port, primary_clk_port = self._get_port_ports(self.primary_port_config)

        mixed_ratios = False
        for secondary_port_config in self.secondary_port_configs:
            if secondary_port_config.mem_ratio != 1:
                mixed_ratios = True
                break

        # It's really hard to generate proper RTL for more than two ports, not to mention that it won't synthesize anyway...
        assert len(self.secondary_port_configs) == 1
        mem_ratio = self.secondary_port_configs[0].mem_ratio

        if mixed_ratios:
            rtl_body =  f"\treg [{mem_ratio-1}:0] [{self.mem_data_bits/mem_ratio-1}:0] mem[0:{mem_addr_range-1}];\n"
        else:
            rtl_body =  f"\treg [{self.mem_data_bits-1}:0] mem[0:{mem_addr_range-1}];\n"
        rtl_body += f"\n"

        if self.config.reset_content is not None:
            rtl_body += f"\tinitial begin\n"
            if callable(self.config.reset_content):
                generator = self.config.reset_content(wider_port_config.data_type.get_num_bits(), mem_addr_range)
                try:
                    for addr in range(1 << addr_bits):
                        data = next(generator)
                        rtl_body += f"\t\tmem[{addr}] <= {data_bits}'h{data:x};\n"
                except StopIteration:
                    pass # memory content is only partially specified
                generator.close()
            else:
                rtl_body += f'\t\t$readmemb("{self.config.reset_content}", mem);\n'
            rtl_body += f"\tend\n"
        rtl_body += f"\n"

        for port_config in self.config.port_configs:
            data_in_port, data_out_port, write_en_port, addr_port, clk_port = self._get_port_ports(port_config)

            data_in, _ = target_namespace._impl.get_rhs_expression_for_junction(data_in_port, back_end) if data_in_port is not None else (None, None)
            data_out = target_namespace._impl.get_lhs_name_for_junction(data_out_port) if data_out_port is not None else None
            write_en, _ = target_namespace._impl.get_rhs_expression_for_junction(write_en_port, back_end) if write_en_port is not None else (None, None)
            addr, _ = target_namespace._impl.get_rhs_expression_for_junction(addr_port, back_end) if addr_port is not None else (None, None)
            clk, _ = target_namespace._impl.get_rhs_expression_for_junction(clk_port, back_end, back_end.get_operator_precedence("()")) if clk_port is not None else (None, None)

            if data_out_port is not None:
                if port_config.registered_input:
                    rtl_body += f"\twire [{port_config.addr_bits-1}:0] {port_config.prefix}addr_reg;\n"
                    addr_name = f"{port_config.prefix}addr_reg"
                else:
                    addr_name = addr
            if data_in_port is not None or (data_out_port is not None and port_config.registered_input):
                rtl_body += f"\talways @(posedge {clk}) begin\n"
                if data_in_port is not None:
                    if write_en_port is not None:
                        rtl_body += f"\t\tif ({write_en}) begin\n"
                        if port_config.mem_ratio == 1:
                            rtl_body += f"\t\t\tmem[{addr}] <= {data_in};\n"
                        else:
                            rtl_body += f"\t\t\tmem[{addr} / {port_config.mem_ratio}][{addr} % {port_config.mem_ratio}] <= {data_in};\n"
                        rtl_body += f"\t\tend\n"
                    else:
                        if port_config.mem_ratio == 1:
                            rtl_body += f"\t\tmem[{addr}] <= {data_in};\n"
                        else:
                            rtl_body += f"\t\tmem[{addr} / {port_config.mem_ratio}][{addr} % {port_config.mem_ratio}] <= {data_in};\n"
                if data_out_port is not None and port_config.registered_input:
                    rtl_body += f"\t\t{addr_name} <= {addr};\n"
                if data_out_port is not None and port_config.registered_output:
                    if port_config.mem_ratio == 1:
                        rtl_body += f"\t\t{data_out} <= mem[{addr_name}];\n"
                    else:
                        rtl_body += f"\t\t{data_out} <= mem[{addr_name} / {port_config.mem_ratio}][{addr_name} % {port_config.mem_ratio}];\n"
                rtl_body += f"\tend\n"
            if data_out_port is not None and not port_config.registered_output:
                if port_config.mem_ratio == 1:
                    rtl_body += f"\t{data_out} <= mem[{addr_name}];\n"
                else:
                    rtl_body += f"\t{data_out} <= mem[{addr_name} / {port_config.mem_ratio}][{addr_name} % {port_config.mem_ratio}];\n"
            rtl_body += f"\n"

        return rtl_body

    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        self._setup()
        rtl_header = self._impl.generate_module_header(back_end)

        # Go through the ports again and make sure they're compatible with the geometry
        if self.get_port_count() == 0:
            raise SyntaxErrorException(f"All memory instances must have at least one port")
        if self.get_port_count() == 1:
            rtl_body = self.generate_single_port_memory(netlist, back_end)
        elif self.get_port_count() == 2:
            rtl_body = self.generate_dual_port_memory(netlist, back_end)
        else:
            raise SyntaxErrorException(f"No more than two ports are supported on memory instances")

        ret_val = (
            str_block(rtl_header, "", "\n\n") +
            str_block(rtl_body, "", "\n") +
            "endmodule"
        )
        return ret_val

    def simulate(self) -> TSimEvent:
        # TODO: load initial content

        self._setup()

        trigger_ports = []
        for port_config in self.config.port_configs:
            _, _, write_en_port, addr_port, clk_port = self._get_port_ports(port_config)
            if port_config.registered_input or port_config.registered_output:
                assert clk_port is not None
                trigger_ports += clk_port
            else:
                trigger_ports += addr_port
                if write_en_port is not None:
                    trigger_ports += write_en_port

        addr_val = None
        data_in_val = None
        write_en_val = None

        memory_content = []
        def get_sim_value(port):
            if port.is_sim_edge():
                return None
            else:
                return port.sim_value

        while True:
            yield trigger_ports
            for port_config in self.config.port_configs:
                data_in_port, data_out_port, write_en_port, addr_port, clk_port = self._get_port_ports(port_config)
                # Deal with the inputs first
                triggered = False
                if port_config.registered_input:
                    if clk_port.is_sim_edge() and clk_port.previous_sim_value == 0 and clk_port.sim_value == 1:
                        triggered = True
                        addr_val = get_sim_value(addr_port)
                        data_in_val = get_sim_value(data_in_port)
                        write_en_val = get_sim_value(write_en_port)
                else:
                    triggered = write_en_port.is_sim_edge and write_en_port.previous_sim_value == 0 and write_en_port.sim_value == 1
                    addr_val = get_sim_value(addr_port)
                    data_in_val = get_sim_value(data_in_port)
                    write_en_val = 1
                if triggered:
                    if write_en_val != 0:
                        pass

                if has_reset and self.reset_port.sim_value == 1:
                    # This branch is never taken for async reset
                    reset()
                else:
                    if self.input_port.is_sim_edge():
                        self.output_port <<= None
                    else:
                        self.output_port <<= self.input_port
