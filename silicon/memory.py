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

from .module import GenericModule, has_port, Module, InlineBlock, InlineStatement
from .port import Input, Output, Wire, AutoInput, Port, EdgeType
from .net_type import NetType
from collections import OrderedDict
from dataclasses import dataclass
from .composite import Struct
from .utils import str_block, is_power_of_two
from .exceptions import SyntaxErrorException
from typing import Optional, Sequence, Generator
from .number import logic, Unsigned
from .utils import TSimEvent, explicit_adapt
from textwrap import indent
from .number import Unsigned

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

class _Memory(GenericModule):
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
                        port_config.real_prefix = ""
                    else:
                        port_config.real_prefix = port_prefix + "_"
                else:
                    port_config.real_prefix = port_config.prefix + "_"
        for port_config in self.config.port_configs:
            setattr(self, f"{port_config.real_prefix}addr", Input(port_config.addr_type))
            self.optional_ports[f"{port_config.real_prefix}data_in"] = (port_config.data_type, Memory.INPUT)
            self.optional_ports[f"{port_config.real_prefix}data_out"] = (port_config.data_type, Memory.OUTPUT)
            self.optional_ports[f"{port_config.real_prefix}write_en"] = (logic, Memory.INPUT)
            setattr(
                self,
                f"{port_config.real_prefix}clk",
                AutoInput(
                    logic,
                    keyword_only = True,
                    auto_port_names = (
                        f"{port_config.real_prefix}clk",
                        f"{port_config.real_prefix}clock",
                        "clk",
                        "clock",
                        f"{port_config.real_prefix}clk_port",
                        f"{port_config.real_prefix}clock_port",
                        "clk_port",
                        "clock_port"
                    ),
                    optional = False
                )
            )

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
        data_in_port = getattr(self, f"{port_config.real_prefix}data_in", None)
        data_out_port = getattr(self, f"{port_config.real_prefix}data_out", None)
        write_en_port = getattr(self, f"{port_config.real_prefix}write_en", None)
        addr_port = getattr(self, f"{port_config.real_prefix}addr")
        clk_port = getattr(self, f"{port_config.real_prefix}clk", None)
        return data_in_port, data_out_port, write_en_port, addr_port, clk_port

    def _setup(self):
        self.primary_port_config = None
        self.secondary_port_configs = []

        has_data_in = False        
        
        for port_config in self.config.port_configs:
            data_conf_bits = port_config.data_type.get_num_bits() if port_config.data_type is not None else None
            addr_conf_bits = port_config.addr_type.get_num_bits() if port_config.addr_type is not None else None

            data_in_port, data_out_port, write_en_port, addr_port, clk_port = self._get_port_ports(port_config)

            has_data_in |= data_in_port is not None

            if data_in_port is None and data_out_port is None:
                raise SyntaxErrorException(f"Memory has neither its read nor its write data connected. That's not a valid use of a memory")
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

        if not has_data_in and self.config.reset_content is None:
            raise SyntaxErrorException(f"For ROMs, reset_content must be specified")

        # Determine memory size
        self.mem_size = 0
        self.mem_data_bits = 0
        for port_config in self.config.port_configs:
            data_bits = port_config.data_bits
            addr_bits = port_config.addr_bits
            self.mem_size = max(self.mem_size, data_bits * (1 << addr_bits))
            self.mem_data_bits = max(data_bits, self.mem_data_bits)
        self.mem_addr_range = self.mem_size // self.mem_data_bits

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

    def generate_reset_content(self, back_end: 'BackEnd', memory_name: str) -> str:
        rtl_body = ""
        if self.config.reset_content is not None:
            rtl_body += f"initial begin\n"
            if callable(self.config.reset_content):
                generator = self.config.reset_content(self.mem_data_bits, self.mem_addr_range)
                try:
                    for addr in range(self.mem_addr_range):
                        data = next(generator)
                        rtl_body += back_end.indent(f"{memory_name}[{addr}] <= {self.mem_data_bits}'h{data:x};\n")
                except StopIteration:
                    pass # memory content is only partially specified
                generator.close()
            else:
                rtl_body += back_end.indent(f'$readmemb("{self.config.reset_content}", mem);\n')
            rtl_body += f"end\n"
            rtl_body += f"\n"

        return rtl_body

    def generate_single_port_memory(self, netlist: 'Netlist', back_end: 'BackEnd', target_namespace: 'Module') -> str:
        # Sing-port memory
        prot_config = self.config.port_configs[0]

        memory_name = netlist.register_symbol(target_namespace, "mem", None)

        data_bits = prot_config.data_bits
        addr_bits = prot_config.addr_bits

        rtl_body =  f"logic [{data_bits-1}:0] {memory_name} [{(1 << addr_bits)-1}:0];\n"

        rtl_body += self.generate_reset_content(back_end, memory_name)

        data_in_port, data_out_port, write_en_port, addr_port, clk_port = self._get_port_ports(prot_config)

        data_in, _ = data_in_port.get_rhs_expression(back_end, target_namespace) if data_in_port is not None else (None, None)
        data_out = data_out_port.get_lhs_name(back_end, target_namespace) if data_out_port is not None else None
        write_en, _ = write_en_port.get_rhs_expression(back_end, target_namespace) if write_en_port is not None else (None, None)
        addr, _ = addr_port.get_rhs_expression(back_end, target_namespace) if addr_port is not None else (None, None)
        clk, _ = clk_port.get_rhs_expression(back_end, target_namespace, None, back_end.get_operator_precedence("()")) if clk_port is not None else (None, None)

        if data_out_port is not None:
            if prot_config.registered_input:
                addr_name = netlist.register_symbol(target_namespace, "addr_reg", None)
                rtl_body += f"logic [{addr_bits-1}:0] {addr_name};\n"
            else:
                addr_name = addr
        if data_in_port is not None or (data_out_port is not None and prot_config.registered_input):
            rtl_body += f"always @(posedge {clk}) begin\n"
            if data_in_port is not None:
                if write_en_port is not None:
                    rtl_body += back_end.indent(f"if ({write_en}) begin\n")
                    rtl_body += back_end.indent(f"{memory_name}[{addr}] <= {data_in};\n", 2)
                    rtl_body += back_end.indent(f"end\n")
                else:
                    rtl_body += back_end.indent(f"{memory_name}[{addr}] <= {data_in};\n")
            if data_out_port is not None and prot_config.registered_input:
                rtl_body += back_end.indent(f"{addr_name} <= {addr};\n")
            if data_out_port is not None and prot_config.registered_output:
                rtl_body += back_end.indent(f"{data_out} <= {memory_name}[{addr_name}];\n")
            rtl_body += f"end\n"
        if data_out_port is not None and not prot_config.registered_output:
            rtl_body += f"assign {data_out} = {memory_name}[{addr_name}];\n"
        return rtl_body

    def generate_dual_port_memory(self, netlist: 'Netlist', back_end: 'BackEnd', target_namespace: 'Module') -> str:
        memory_name = netlist.register_symbol(target_namespace, "mem", None)

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
            rtl_body =  f"reg [{mem_ratio-1}:0] [{self.mem_data_bits/mem_ratio-1}:0] {memory_name}[0:{self.mem_addr_range-1}];\n"
        else:
            rtl_body =  f"reg [{self.mem_data_bits-1}:0] {memory_name}[0:{self.mem_addr_range-1}];\n"
        rtl_body += f"\n"

        rtl_body += self.generate_reset_content(back_end, memory_name)

        for port_config in self.config.port_configs:
            data_in_port, data_out_port, write_en_port, addr_port, clk_port = self._get_port_ports(port_config)

            data_in, _ = data_in_port.get_rhs_expression(back_end, target_namespace) if data_in_port is not None else (None, None)
            data_out = data_out_port.get_lhs_name(back_end, target_namespace) if data_out_port is not None else None
            write_en, _ = write_en_port.get_rhs_expression(back_end, target_namespace) if write_en_port is not None else (None, None)
            addr, _ = addr_port.get_rhs_expression(back_end, target_namespace) if addr_port is not None else (None, None)
            clk, _ = clk_port.get_rhs_expression(back_end, target_namespace, None, back_end.get_operator_precedence("()")) if clk_port is not None else (None, None)

            if data_out_port is not None:
                if port_config.registered_input:
                    addr_name = netlist.register_symbol(target_namespace, f"{port_config.real_prefix}addr_reg", None)
                    rtl_body += f"logic [{port_config.addr_bits-1}:0] {addr_name};\n"
                else:
                    addr_name = addr
            if data_in_port is not None or (data_out_port is not None and port_config.registered_input):
                rtl_body += f"always @(posedge {clk}) begin\n"
                if data_in_port is not None:
                    if write_en_port is not None:
                        rtl_body += back_end.indent(f"if ({write_en}) begin\n")
                        if port_config.mem_ratio == 1:
                            rtl_body += back_end.indent(f"{memory_name}[{addr}] <= {data_in};\n", 2)
                        else:
                            rtl_body += back_end.indent(f"{memory_name}[{addr} / {port_config.mem_ratio}][{addr} % {port_config.mem_ratio}] <= {data_in};\n", 2)
                        rtl_body += back_end.indent(f"end\n")
                    else:
                        if port_config.mem_ratio == 1:
                            rtl_body += back_end.indent(f"{memory_name}[{addr}] <= {data_in};\n")
                        else:
                            rtl_body += back_end.indent(f"{memory_name}[{addr} / {port_config.mem_ratio}][{addr} % {port_config.mem_ratio}] <= {data_in};\n")
                if data_out_port is not None and port_config.registered_input:
                    rtl_body += back_end.indent(f"{addr_name} <= {addr};\n")
                if data_out_port is not None and port_config.registered_output:
                    if port_config.mem_ratio == 1:
                        rtl_body += back_end.indent(f"{data_out} <= {memory_name}[{addr_name}];\n")
                    else:
                        rtl_body += back_end.indent(f"{data_out} <= {memory_name}[{addr_name} / {port_config.mem_ratio}][{addr_name} % {port_config.mem_ratio}];\n")
                rtl_body += f"end\n"
            if data_out_port is not None and not port_config.registered_output:
                if port_config.mem_ratio == 1:
                    rtl_body += f"assign {data_out} = {memory_name}[{addr_name}];\n"
                else:
                    rtl_body += f"assign {data_out} = {memory_name}[{addr_name} / {port_config.mem_ratio}][{addr_name} % {port_config.mem_ratio}];\n"
            rtl_body += f"\n"

        return rtl_body

    def get_inline_block(self, back_end: 'BackEnd', target_namespace: 'Module') -> Generator[InlineBlock, None, None]:
        yield InlineStatement(self.get_outputs().values(), self.generate_inline_statement(back_end, target_namespace))

    def generate_inline_statement(self, back_end: 'BackEnd', target_namespace: 'Module') -> str:
        self._setup()
        #rtl_header = self._impl.generate_module_header(back_end)

        # Go through the ports again and make sure they're compatible with the geometry
        if self.get_port_count() == 0:
            raise SyntaxErrorException(f"All memory instances must have at least one port")
        if self.get_port_count() == 1:
            rtl_body = self.generate_single_port_memory(self._impl.netlist, back_end, target_namespace)
        elif self.get_port_count() == 2:
            rtl_body = self.generate_dual_port_memory(self._impl.netlist, back_end, target_namespace)
        else:
            raise SyntaxErrorException(f"No more than two ports are supported on memory instances")

        #ret_val = (
        #    str_block(rtl_header, "", "\n\n") +
        #    str_block(back_end.indent(rtl_body), "", "\n") +
        #    "endmodule"
        #)
        return rtl_body

    #def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:

    def simulate(self) -> TSimEvent:
        # TODO: load initial content

        self._setup()

        trigger_ports = []
        for port_config in self.config.port_configs:
            _, _, write_en_port, addr_port, clk_port = self._get_port_ports(port_config)
            if port_config.registered_input or port_config.registered_output:
                assert clk_port is not None
                trigger_ports.append(clk_port)
            else:
                trigger_ports.append(addr_port)
                if write_en_port is not None:
                    trigger_ports.append(write_en_port)

        addr_val = None
        data_in_val = None
        write_en_val = None

        # Memory holds entries for the narrowest port.
        # Wider ports do multiple consequtive accesses based on endienness.
        memory_content = []

        mem_data_bits = self.config.port_configs[0].data_bits
        mem_addr_bits = self.config.port_configs[0].addr_bits
        for port_config in self.config.port_configs[1:]:
            mem_data_bits = min(mem_data_bits, port_config.data_bits)
            mem_addr_bits = min(mem_addr_bits, port_config.addr_bits)
        
        def get_sim_value(port):
            if port.get_sim_edge() != EdgeType.NoEdge:
                return None
            else:
                return port.sim_value

        def set_mem_val(addr, data):
            while len(memory_content) <= addr:
                memory_content.append(None)
            memory_content[addr] = data
        def get_mem_val(addr):
            if addr >= len(memory_content):
                return None
            return memory_content[addr]

        last_read_values = [None] * self.get_port_count()

        while True:
            yield trigger_ports
            for idx, port_config in enumerate(self.config.port_configs):
                data_in_port, data_out_port, write_en_port, addr_port, clk_port = self._get_port_ports(port_config)
                # Deal with the inputs first
                write = False
                read = False
                read_invalid = False
                addr_val = get_sim_value(addr_port)
                data_in_val = get_sim_value(data_in_port)
                write_en_val = get_sim_value(write_en_port)
                if port_config.registered_input:
                    clk_edge_type = clk_port.get_sim_edge()
                    if clk_edge_type == EdgeType.Positive:
                        write = write_en_port is None or write_en_val != 0
                        read = True
                        if port_config.registered_output:
                            data_out_port <<= last_read_values[idx]
                    if clk_edge_type == EdgeType.Undefined:
                        # In this case we don't know if a write or read happens or not. So make sure that data is X-ed out
                        write = write_en_port is None or write_en_val != 0
                        read = True
                        data_in_val = None
                        read_invalid = True
                else:
                    write_edge_type = write_en_port.get_sim_edge()
                    if write_edge_type == EdgeType.Positive:
                        write = True
                    if write_edge_type == EdgeType.Undefined:
                        write = True
                        data_in_val = None
                    read = addr_port.get_sim_edge() != EdgeType.NoEdge
                if write:
                    if addr_val is None:
                        # We don't know where we write. For now, let's invalidate the whole memory...
                        memory_content = []
                    else:
                        burst_size = port_config.data_bits // mem_data_bits
                        start_addr = addr_val * burst_size
                        data_mask = (1 << port_config.data_bits) - 1
                        for addr in range(start_addr, start_addr + burst_size):
                            if data_in_val is None:
                                set_mem_val(addr, None)
                            else:
                                set_mem_val(addr, data_in_val & data_mask)
                                data_in_val >>= port_config.data_bits
                if read and data_out_port is not None:
                    if read_invalid or addr_val is None:
                        data_out_port <<= None
                    else:
                        data_out_val = 0
                        burst_size = port_config.data_bits // mem_data_bits
                        start_addr = addr_val * burst_size
                        data_mask = (1 << port_config.data_bits) - 1
                        for addr in range(start_addr + burst_size - 1, start_addr - 1, -1):
                            data_section = get_mem_val(addr)
                            if data_section is None:
                                data_out_val = None
                                break
                            data_out_val = (data_out_val >> port_config.data_bits) | (data_section & data_mask)
                        last_read_values[idx] = data_out_val
                        if not port_config.registered_output:
                            data_out_port <<= data_out_val


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
                        port_config.real_prefix = ""
                    else:
                        port_config.real_prefix = port_prefix + "_"
                else:
                    port_config.real_prefix = port_config.prefix + "_"
        for port_config in self.config.port_configs:
            setattr(self, f"{port_config.real_prefix}addr", Input(port_config.addr_type))
            self.optional_ports[f"{port_config.real_prefix}data_in"] = (port_config.data_type, Memory.INPUT)
            self.optional_ports[f"{port_config.real_prefix}data_out"] = (port_config.data_type, Memory.OUTPUT)
            self.optional_ports[f"{port_config.real_prefix}write_en"] = (logic, Memory.INPUT)
            setattr(
                self,
                f"{port_config.real_prefix}clk",
                AutoInput(
                    logic,
                    keyword_only = True,
                    auto_port_names = (
                        f"{port_config.real_prefix}clk",
                        f"{port_config.real_prefix}clock",
                        "clk",
                        "clock",
                        f"{port_config.real_prefix}clk_port",
                        f"{port_config.real_prefix}clock_port",
                        "clk_port",
                        "clock_port"
                    ),
                    optional = False
                )
            )

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

    def body(self):
        from copy import deepcopy
        # Replace all data types with their equivalent number types
        mem_config = deepcopy(self.config)
        for port_config in mem_config.port_configs:
            port_config.data_type = Unsigned(port_config.data_type.get_num_bits())
        real_mem = _Memory(mem_config)
        # Hook up all of our ports to the internal one
        for port_name, port in self.get_inputs().items():
            if port_name.endswith("data_in"):
                port = explicit_adapt(port, Unsigned(length=port.get_num_bits()))
            setattr(real_mem, port_name, port)
        for port_name, port in self.get_outputs().items():
            if port_name.endswith("data_out"):
                port <<= explicit_adapt(getattr(real_mem, port_name), port.get_net_type())
            else:
                port <<= getattr(real_mem, port_name)
        port = None # Make sure tracer doesn't generate an unnecessary Wire object