# Memories have soooooo many variants, not even counting memory-compilers.
# What we support probably should support:
#
# MEMORY TYPE (both are supported)
# - ROM
# - RAM
# PORT CONFIGURATION (all supported)
# - Up to 2 ports
# - Read-only ports
# - Write-only ports
# - Read-write ports
# - Independent widths on each port
# READ PORTS (all supported)
# - 0-cycle latency (asynchronous access)
# - 1-cycle latency (registered data)
# - 2-cycle latency (registered address and data)
# WRITE PORTS
# - Byte-enables (or maybe section-enables?) <--- WE ONLY SUPPORT A SINGLE WRITE_ENABLE SIGNAL
# - 0-cycle latency
# - 1-cycle latency (registered address and data)
# READ-WRITE PORTS
# - All of the above, plus:
# - WRITE_FIRST (output data = write data during writes)        <--- I DON'T THINK WE SUPPORT THIS!!!
# - READ_FIRST (output data = old memory condent during writes) <--- THIS IS WHAT WE SUPPORT
# - NO_CHANGE (output data = data from last read during writes) <--- I DON'T THINK WE SUPPORT THIS!!!
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
# ERROR-CORRECTION (only 'none' is supported)
# - None
# - Parity
# - ECC (might add extra latency)
# - ECC with auto-correct (needs read-modify-write cycles for failed reads)
# POWER MANAGEMENT (only 'none' is supported)
# - None
# - Clock-gating (retention)
# - Power-gating
# CONTENT MANAGEMENT (RAM) (only 'initial content' is supported)
# - Initial content
# - Reset to zero (sync/async)
# - Undefined on power-on
# CONTENT MANAGEMENT (ROM) (supported)
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
# - It appears that no one (not even ASIC vendors) support more than 2 ports on SRAM arrays. So the two-port restriction seems prudent.
#    - That still leaves out register files, that can have many many ports. It might be worth breaking that application out though.
# - Memory compiler vendors:
#    - Synopsys
#    - ARM (Artisan)
#    - Essentially 'contact your foundry'
#    - There's a 'fake' memory generator, called 'OpenRAM' that can be used for experimentation
#    - There's another 'fake' memory generator, called CACTI (https://www.hpl.hp.com/research/cacti/)
#      that only generates size/power models but can still be useful potentially.

from .module import GenericModule, has_port, Module, InlineBlock, InlineStatement
from .port import Input, Output, Wire, Port, EdgeType, Junction
from .auto_input import ClkPort
from .net_type import NetType
from collections import OrderedDict
from dataclasses import dataclass
from .composite import Struct
from .utils import str_block, is_power_of_two, first
from .sym_table import SymbolTable
from .netlist import Netlist
from .exceptions import SyntaxErrorException, InvalidPortError
from typing import Optional, Sequence, Generator, Union, List, BinaryIO, Callable
from .number import logic, Unsigned
from .utils import TSimEvent, explicit_adapt
from textwrap import indent
from .number import Unsigned, is_number
from .primitives import Reg, Select
from io import BytesIO


def init_mem(init_content, content_width, content_depth):
    leftover_bit_cnt = 0
    leftover_bits = 0
    def mask(bits) -> int: return (1 << bits) - 1
    def read_bits(f: BinaryIO, count: int) -> int:
        nonlocal leftover_bit_cnt, leftover_bits
        bytes_to_read = (count - leftover_bit_cnt + 7) // 8
        new_bytes = f.read(bytes_to_read)
        eof = len(new_bytes) < bytes_to_read
        if eof:
            count = len(new_bytes) * 8 + leftover_bit_cnt
        if count == 0 and len(new_bytes) == 0:
            raise EOFError()
        if count <= leftover_bit_cnt:
            ret_val = leftover_bits & mask(count)
            leftover_bit_cnt -= count
            leftover_bits >>= count
            return ret_val
        ret_val = leftover_bits
        count -= leftover_bit_cnt
        shift = leftover_bit_cnt
        idx = 0
        while count > 8:
            ret_val |= new_bytes[idx] << shift
            count -= 8
            idx += 1
            shift += 8
        ret_val |= (new_bytes[idx] & mask(count)) << shift
        leftover_bit_cnt = 8-count
        leftover_bits = new_bytes[idx] >> (8-count) if count < 8 else 0
        return ret_val

    content = {}
    if init_content is not None:
        if callable(init_content):
            generator = init_content(content_width, content_depth)
            try:
                for idx in range(content_depth):
                    data = next(generator)
                    content[idx] = data
            except StopIteration:
                pass # memory content is only partially specified
            generator.close()
        elif isinstance(init_content, str):
            f = open(init_content, "rt")
            with f:
                try:
                    idx = 0
                    for line in f:
                        values = line.split()
                        for value in values:
                            int_val = int(value, base=16)
                            content[idx] = int_val
                            idx += 1
                            if idx > content_depth:
                                break
                except EOFError:
                    pass
        else:
            f = BytesIO(init_content)
            with f:
                try:
                    for idx in range(content_depth):
                        content[idx] = read_bits(f, content_width)
                except EOFError:
                    pass
    return content
class _BasicMemory(GenericModule):
    class MemoryPort(object):
        def __init__(self):
            self.data_in = Input(default_value=None)
            self.write_en = Input(default_value=0)
            self.write_clk = Input(default_value=0)
            self.addr = Input()
            self.data_out = Output()

    def construct(self, port_cnt: int, init_content: Optional[Union[str, Callable]] = None):
        self.mem_ports: List[_BasicMemory.MemoryPort] = []
        self.do_log = False
        self.init_content = init_content
        for idx in range(port_cnt):
            port = _BasicMemory.MemoryPort()
            setattr(self, f"data_in_{idx}_port", port.data_in)
            setattr(self, f"write_en_{idx}_port", port.write_en)
            setattr(self, f"write_clk_{idx}_port", port.write_clk)
            setattr(self, f"addr_{idx}_port", port.addr)
            setattr(self, f"data_out_{idx}_port", port.data_out)
            self.mem_ports.append(port)

    def set_port_type(self, port_idx: int, net_type: NetType):
        if port_idx > len(self.mem_ports):
            raise SyntaxErrorException(f"_BasicMemory {self} doesn't have a port {port_idx}")
        port = self.mem_ports[port_idx]
        if not is_number(net_type):
            raise SyntaxErrorException(f"_BasicMemory {self} only support Number-based interface types")
        port.data_out.set_net_type(net_type)
        port.data_in.set_net_type(net_type)

    def body(self):
        self.content_trigger = Wire(logic)

    def generate(self):
        raise SyntaxErrorException("BasicMem is a simulation model only. RTL generation is not supported.")

    def _setup(self):
        for idx, port in enumerate(self.mem_ports):
            try:
                try:
                    port.width = port.data_in.get_net_type().get_num_bits()
                    if not is_number(port.data_in.get_net_type()):
                        raise SyntaxErrorException(f"_BasicMemory {self} only support Number-based interface types")
                except AttributeError:
                    port.width = port.data_out.get_net_type().get_num_bits()
            except AttributeError:
                raise SyntaxErrorException(f"Memory port {idx} for {self} has neither its data input or output connected")

            try:
                port.depth = 2 ** port.addr.get_net_type().get_num_bits()
                if not is_number(port.addr.get_net_type()):
                    raise SyntaxErrorException(f"_BasicMemory {self} only support Number-based interface types")
            except AttributeError:
                raise SyntaxErrorException(f"Memory port {idx} for {self} has doesn't have its address port connected")
            port.has_read = port.data_out.get_net_type() is not None # Not precise, but good enough: the only reason reads would fail if the output junction has no type
            port.mem_size_in_bits = port.depth * port.width

        max_width = max(port.width for port in self.mem_ports)
        for idx, port in enumerate(self.mem_ports):
            if max_width % port.width != 0:
                raise SyntaxErrorException(f"Memory width {max_width} is not divisible by width {port.width} of port {idx} for {self}.")



    def simulate(self, simulator: 'Simulator') -> TSimEvent:
        # We have some optional ports, but those would have drivers by this stage: a constant 'None' or '0' driver
        # We will simply trigger on all write_en and address ports, plus our own internal content_trigger
        trigger_ports = []
        for port in self.mem_ports:
            trigger_ports.append(port.write_clk)
            trigger_ports.append(port.addr)
        trigger_ports.append(self.content_trigger)

        self._setup()
        content_width = min(port.width for port in self.mem_ports)
        content_depth = 0
        for port in self.mem_ports:
            content_depth = max(content_depth, port.mem_size_in_bits//content_width)
        content = init_mem(
            self.init_content,
            content_width,
            content_depth
        )


        def read_mem(addr: int, data_width: int) -> int:
            value = 0
            burst_size = data_width // content_width
            start_addr = addr * burst_size
            data_mask = (1 << content_width) - 1
            for burst_addr in range(start_addr + burst_size - 1, start_addr - 1, -1):
                try:
                    data_section = content[burst_addr]
                except KeyError:
                    return None
                if data_section is None:
                    return None
                value = (value << content_width) | (data_section & data_mask)
            return value

        def write_mem(addr:int, value: int, data_width: int):
            burst_size = data_width // content_width
            start_addr = addr * burst_size
            data_mask = (1 << content_width) - 1
            burst_value = value
            for burst_addr in range(start_addr, start_addr + burst_size):
                if burst_value is not None:
                    content[burst_addr] = burst_value & data_mask
                    burst_value >>= content_width
                else:
                    content[burst_addr] = None

        while True:
            yield trigger_ports

            if self.do_log: simulator.log("Memory got triggered")
            # This is an asynchronous memory with 'read-old-value' behavior.
            # However, if any writes are performed, that will trigger a 'content_trigger' change
            # So we will come back in the next delta step and do another read. This behavior
            # is good enough to capture the output in registers, if needed, but also properly
            # simulates the fact that this is an asynchronous array
            for idx, port in enumerate(self.mem_ports):
                # Read ports should only care about content and address changes
                if port.addr.get_sim_edge() == EdgeType.NoEdge and self.content_trigger.get_sim_edge() == EdgeType.NoEdge:
                    continue
                if not port.has_read:
                    continue
                try:
                    addr = int(port.addr.sim_value)
                except (TypeError, ValueError):
                    port.data_out <<= None
                    continue
                raw_value = read_mem(addr, port.width)
                if self.do_log: simulator.log(f"reading port {idx} addr {addr} returning value {raw_value}")
                port.data_out <<= raw_value

            for idx, port in enumerate(self.mem_ports):
                we_edge_type = port.write_clk.get_sim_edge()
                if we_edge_type == EdgeType.Undefined:
                    # We don't know if there was an edge: clear the whole memory
                    if port.write_en != 0 and simulator.now > 0:
                        content.clear()
                    self.content_trigger <<= 1 if self.content_trigger == 0 else 0
                    continue
                if we_edge_type == EdgeType.Positive:
                    if port.write_en == 1:
                        try:
                            addr = int(port.addr.sim_value)
                        except (TypeError, ValueError):
                            # There was an edge, but we don't know which address was written: clear the whole memory
                            content.clear()
                            self.content_trigger <<= 1 if self.content_trigger == 0 else 0
                            continue
                        try:
                            raw_value = int(port.data_in.sim_value)
                        except (TypeError, ValueError):
                            raw_value = None

                        if self.do_log: simulator.log(f"writing port {idx} addr {addr} with value {raw_value}")
                        write_mem(addr, raw_value, port.width)

                        self.content_trigger <<= 1 if self.content_trigger == 0 else 0
                    elif port.write_en == None:
                        content.clear()
                        self.content_trigger <<= 1 if self.content_trigger == 0 else 0

                    if self.do_log: simulator.log(f"     content: {content}")



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
    init_content: Optional[Union[str, Callable]] = None

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
        self.primary_port_config = None
        self.secondary_port_configs = []
        self.mem_size = None
        self.mem_data_bits = None
        self.mem_max_data_bits = None
        self.mem_addr_range = None
        self.addr_reg_symbols = []
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
                ClkPort(
                    auto_port_names = (
                        f"{port_config.real_prefix}clk",
                        f"{port_config.real_prefix}clock",
                        "clk",
                        "clock",
                        f"{port_config.real_prefix}clk_port",
                        f"{port_config.real_prefix}clock_port",
                        "clk_port",
                        "clock_port"
                    )
                )
            )
            self.addr_reg_symbols.append(self._create_symbol(f"{port_config.real_prefix}addr_reg"))
        self.mem_symbol = self._create_symbol("mem")
        if len(self.addr_reg_symbols) == 0:
            self.addr_reg_symbols.append(self._create_symbol("addr_reg"))

    def create_named_port_callback(self, name: str, net_type: Optional['NetType'] = None) -> Optional[Port]:
        """
        Called from the framework when unknown ports are accessed. This allows for dynamic port creation, though the default is to do nothing.
        Port creation should be as restrictive as possible and for any non-supported name, return None.
        This allows for regular attribute creation for non-port attributes.
        NOTE: create_named_port_callback should return the created port object instead of directly adding it to self
        """
        if name in self.optional_ports:
            if net_type is not None and net_type is not self.optional_ports[name][0]:
                raise SyntaxErrorException("Net type '{net_type}' is not valid for optional port '{name}'")
            if self.optional_ports[name][1] == Memory.INPUT:
                return Input(self.optional_ports[name][0])
            elif self.optional_ports[name][1] == Memory.OUTPUT:
                return Output(self.optional_ports[name][0])
            else:
                assert False
        raise InvalidPortError()

    def get_port_count(self) -> int:
        return len(self.config.port_configs)

    def _get_port_ports(self, port_config) -> Sequence[Port]:
        data_in_port = getattr(self, f"{port_config.real_prefix}data_in", None)
        data_out_port = getattr(self, f"{port_config.real_prefix}data_out", None)
        write_en_port = getattr(self, f"{port_config.real_prefix}write_en", None)
        addr_port = getattr(self, f"{port_config.real_prefix}addr")
        clk_port = getattr(self, f"{port_config.real_prefix}clk", None)
        clk_en_port = getattr(self, f"{port_config.real_prefix}clk_en", None)
        return data_in_port, data_out_port, write_en_port, addr_port, clk_port, clk_en_port

    def _setup(self):
        has_data_in = False

        for port_config in self.config.port_configs:
            data_conf_bits = port_config.data_type.get_num_bits() if port_config.data_type is not None else None
            addr_conf_bits = port_config.addr_type.get_num_bits() if port_config.addr_type is not None else None

            data_in_port, data_out_port, write_en_port, addr_port, clk_port, clk_en_port = self._get_port_ports(port_config)

            has_data_in |= data_in_port is not None

            if data_in_port is None and data_out_port is None:
                raise SyntaxErrorException(f"Memory has neither its read nor its write data connected. That's not a valid use of a memory")
            if write_en_port is not None and data_in_port is None:
                raise SyntaxErrorException("If a memory has a write-enable, it must have a corresponding data")
            #if not port_config.registered_input and data_in_port is not None:
            #    raise SyntaxErrorException("Unregistered inputs are only supported for read ports on inferred memories")

            if data_in_port is not None:
                data_in_bits = data_in_port.get_net_type().get_num_bits()
                if data_conf_bits is not None and data_conf_bits < data_in_bits:
                    raise SyntaxErrorException(f"Memory was specified as {data_conf_bits} wide in config, yet data input port is {data_in_bits} wide")
            if data_out_port is not None:
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

        if not has_data_in and self.config.init_content is None:
            raise SyntaxErrorException(f"For ROMs, init_content must be specified")

        # Determine memory size
        self.mem_size = 0
        self.mem_max_data_bits = 0
        self.mem_data_bits = None
        for port_config in self.config.port_configs:
            data_bits = port_config.data_bits
            addr_bits = port_config.addr_bits
            self.mem_size = max(self.mem_size, data_bits * (1 << addr_bits))
            self.mem_max_data_bits = max(data_bits, self.mem_max_data_bits)
            self.mem_data_bits = data_bits if self.mem_data_bits is None else min(data_bits, self.mem_data_bits)
        self.mem_addr_range = self.mem_size // self.mem_data_bits

        # Finding primary and secondary ports, while checking for port compatibility
        for port_config in self.config.port_configs:
            data_bits = port_config.data_bits
            if self.mem_max_data_bits % data_bits != 0:
                raise SyntaxErrorException(f"For multi-port memories, data sizes on all ports must be integer multiples of one another")
            ratio = self.mem_max_data_bits // data_bits
            if not is_power_of_two(ratio):
                raise SyntaxErrorException(f"For multi-port memories, data size ratios must be powers of 2")

            port_config.mem_ratio = ratio
            if ratio == 1 and self.primary_port_config is None:
                self.primary_port_config = port_config
            else:
                self.secondary_port_configs.append(port_config)

        # Checking port interactions
        primary_data_in_port, primary_data_out_port, _, _, _, _ = self._get_port_ports(self.primary_port_config)

        has_data_in = primary_data_in_port is not None
        has_data_out = primary_data_out_port is not None
        for secondary_port_config in self.secondary_port_configs:
            secondary_data_in_port, secondary_data_out_port, _, _, _, _ = self._get_port_ports(secondary_port_config)
            has_data_in |= secondary_data_in_port is not None
            has_data_out |= secondary_data_out_port is not None

        if not has_data_in and not has_data_out:
            raise SyntaxErrorException(f"Memory has neither its read nor its write data connected. That's not a valid use of a memory")
        if not has_data_in and self.config.init_content is None:
            raise SyntaxErrorException(f"For ROMs, init_content must be specified")

    def body(self):
        self._setup()

        inner_mem = _BasicMemory(len(self.config.port_configs), self.config.init_content)
        #inner_mem.do_log = True
        for idx, port_config in enumerate(self.config.port_configs):
            inner_mem.set_port_type(idx, Unsigned(port_config.data_type.get_num_bits()))
            data_in_port, data_out_port, write_en_port, addr_port, clk_port, clk_en_port = self._get_port_ports(port_config)
            if write_en_port is None: write_en_port = 0
            if port_config.registered_input:
                addr_port = Reg(addr_port, clock_port=clk_port, clock_en=clk_en_port)
                data_in_port = Reg(data_in_port, clock_port=clk_port, clock_en=clk_en_port)
                write_en_port = Reg(write_en_port, clock_port=clk_port, clock_en=clk_en_port)
            async_data_out = getattr(inner_mem, f"data_out_{idx}_port")
            if data_out_port is not None:
                data_out_port <<= Reg(async_data_out, clock_port=clk_port, clock_en=clk_en_port) if port_config.registered_output else Select(write_en_port, async_data_out, data_in_port)
            inner_data_in = getattr(inner_mem, f"data_in_{idx}_port")
            inner_addr = getattr(inner_mem, f"addr_{idx}_port")
            inner_write_en = getattr(inner_mem, f"write_en_{idx}_port")
            inner_write_clk = getattr(inner_mem, f"write_clk_{idx}_port")
            inner_data_in <<= data_in_port
            inner_addr <<= addr_port
            inner_write_en <<= write_en_port
            inner_write_clk <<= clk_port

    def generate_init_content(self, back_end: 'BackEnd', memory_name: str) -> str:
        rtl_body = ""
        if self.config.init_content is not None:
            rtl_body += f"initial begin\n"
            with back_end.indent_block():
                if isinstance(self.config.init_content, str):
                    rtl_body += back_end.indent(f'$readmemh("{self.config.init_content}", mem);\n')
                else:
                    content = init_mem(self.config.init_content, self.mem_data_bits, self.mem_addr_range)
                    factor2d = self.mem_max_data_bits // self.mem_data_bits
                    for addr, data in content.items():
                        if factor2d != 1:
                            outer_addr = addr // factor2d
                            inner_addr = addr % factor2d
                            rtl_body += back_end.indent(f"{memory_name}[{outer_addr}][{inner_addr}] <= {self.mem_data_bits}'h{data:x};\n")
                        else:
                            rtl_body += back_end.indent(f"{memory_name}[{addr}] <= {self.mem_data_bits}'h{data:x};\n")
            rtl_body += f"end\n"
            rtl_body += f"\n"

        return rtl_body

    def _create_symbol(self, base_name: str) -> object:
        class Instance(object): pass
        instance = Instance()
        scope_table = self._impl.netlist.symbol_table[self]
        scope_table.add_soft_symbol(instance, base_name)
        return instance

    def _get_symbol_name(self, netlist: 'Netlist', obj: object) -> str:
        return first(netlist.symbol_table[self].get_names(obj))

    def generate_single_port_memory(self, netlist: 'Netlist', back_end: 'BackEnd', target_namespace: 'Module') -> str:
        # Sing-port memory
        port_config = self.config.port_configs[0]

        memory_name = self._get_symbol_name(netlist, self.mem_symbol)

        data_bits = port_config.data_bits
        addr_bits = port_config.addr_bits

        rtl_body =  f"logic [{data_bits-1}:0] {memory_name} [0:{(1 << addr_bits)-1}];\n"

        rtl_body += self.generate_init_content(back_end, memory_name)

        data_in_port, data_out_port, write_en_port, addr_port, clk_port, clk_en_port = self._get_port_ports(port_config)

        data_in, _ = data_in_port.get_rhs_expression(back_end, target_namespace) if data_in_port is not None else (None, None)
        data_out = data_out_port.get_lhs_name(back_end, target_namespace) if data_out_port is not None else None
        write_en, _ = write_en_port.get_rhs_expression(back_end, target_namespace) if write_en_port is not None else (None, None)
        addr, _ = addr_port.get_rhs_expression(back_end, target_namespace) if addr_port is not None else (None, None)
        clk, _ = clk_port.get_rhs_expression(back_end, target_namespace, None, back_end.get_operator_precedence("()")) if clk_port is not None else (None, None)
        clk_en, _ = clk_en_port.get_rhs_expression(back_end, target_namespace) if clk_en_port is not None else (None, None)

        if data_out_port is not None:
            if port_config.registered_input:
                addr_name = self._get_symbol_name(netlist, self.addr_reg_symbols[0])
                rtl_body += f"logic [{addr_bits-1}:0] {addr_name};\n"
            else:
                addr_name = addr
        if data_in_port is not None or (data_out_port is not None and port_config.registered_input):
            rtl_body += f"always @(posedge {clk}) begin\n"
            with back_end.indent_block():
                if clk_en_port is not None:
                    rtl_body += back_end.indent(f"if ({clk_en}) begin\n")
                with back_end.indent_block(clk_en_port is not None):
                    if data_in_port is not None:
                        if write_en_port is not None:
                            rtl_body += back_end.indent(f"if ({write_en}) begin\n")
                            with back_end.indent_block():
                                rtl_body += back_end.indent(f"{memory_name}[{addr}] <= {data_in};\n")
                            rtl_body += back_end.indent(f"end\n")
                        else:
                            rtl_body += back_end.indent(f"{memory_name}[{addr}] <= {data_in};\n")
                    if data_out_port is not None and port_config.registered_input:
                        rtl_body += back_end.indent(f"{addr_name} <= {addr};\n")
                    if data_out_port is not None and port_config.registered_output:
                        rtl_body += back_end.indent(f"{data_out} <= {memory_name}[{addr_name}];\n")
                if clk_en_port is not None:
                    rtl_body += back_end.indent(f"end\n")
            rtl_body += f"end\n"
        if data_out_port is not None and not port_config.registered_output:
            rtl_body += f"assign {data_out} = {memory_name}[{addr_name}];\n"
        return rtl_body

    def generate_dual_port_memory(self, netlist: 'Netlist', back_end: 'BackEnd', target_namespace: 'Module') -> str:
        memory_name = self._get_symbol_name(netlist, self.mem_symbol)

        rtl_body = ""

        mixed_ratios = False
        for secondary_port_config in self.secondary_port_configs:
            if secondary_port_config.mem_ratio != 1:
                mixed_ratios = True
                break

        # It's really hard to generate proper RTL for more than two ports, not to mention that it won't synthesize anyway...
        assert len(self.secondary_port_configs) == 1
        mem_ratio = self.secondary_port_configs[0].mem_ratio

        if mixed_ratios:
            rtl_body =  f"reg [{mem_ratio-1}:0] [{self.mem_data_bits-1}:0] {memory_name} [0:{self.mem_addr_range-1}];\n"
        else:
            rtl_body =  f"reg [{self.mem_data_bits-1}:0] {memory_name} [0:{self.mem_addr_range-1}];\n"
        rtl_body += f"\n"

        rtl_body += self.generate_init_content(back_end, memory_name)

        for idx, port_config in enumerate(self.config.port_configs):
            data_in_port, data_out_port, write_en_port, addr_port, clk_port, clk_en_port = self._get_port_ports(port_config)

            data_in, _ = data_in_port.get_rhs_expression(back_end, target_namespace) if data_in_port is not None else (None, None)
            data_out = data_out_port.get_lhs_name(back_end, target_namespace) if data_out_port is not None else None
            write_en, _ = write_en_port.get_rhs_expression(back_end, target_namespace) if write_en_port is not None else (None, None)
            addr, _ = addr_port.get_rhs_expression(back_end, target_namespace) if addr_port is not None else (None, None)
            clk, _ = clk_port.get_rhs_expression(back_end, target_namespace, None, back_end.get_operator_precedence("()")) if clk_port is not None else (None, None)
            clk_en, _ = clk_en_port.get_rhs_expression(back_end, target_namespace) if clk_en_port is not None else (None, None)

            if data_out_port is not None:
                if port_config.registered_input:
                    addr_name = self._get_symbol_name(netlist, self.addr_reg_symbols[idx])
                    rtl_body += f"logic [{port_config.addr_bits-1}:0] {addr_name};\n"
                else:
                    addr_name = addr
            # We have a ton of case to consider:
            #  data_in    data_out    reg_in   reg_out
            #    -            -          ?        ?     -> no RTL needed (4 cases)
            #    Yes          -          -        ?     -> not supported (2 cases)
            #    Yes          Yes        -        ?     -> not supported (2 cases)

            #    Yes          -          Yes      ?     -> first and second if statements (2 cases)
            #    Yes          Yes        Yes      ?     -> first and second if statements (2 cases)
            #    -            Yes        -        -     -> second if
            #    -            Yes        -        Yes
            #    -            Yes        Yes      -     -> first and second if statements (2 cases)
            #    -            Yes        Yes      Yes

            if data_in_port is not None or (data_out_port is not None and port_config.registered_input):
                rtl_body += back_end.indent(f"always @(posedge {clk}) begin\n")
                with back_end.indent_block():
                    if clk_en_port is not None:
                        rtl_body += back_end.indent(f"if ({clk_en}) begin\n")
                    with back_end.indent_block(clk_en_port is not None):
                        with back_end.indent_block(clk_en_port is not None):
                            if data_in_port is not None:
                                if write_en_port is not None:
                                    rtl_body += back_end.indent(f"if ({write_en}) begin\n")
                                with back_end.indent_block(write_en_port is not None):
                                    if port_config.mem_ratio == 1:
                                        rtl_body += back_end.indent(f"{memory_name}[{addr}] <= {data_in};\n")
                                    else:
                                        rtl_body += back_end.indent(f"{memory_name}[{addr} / {port_config.mem_ratio}][{addr} % {port_config.mem_ratio}] <= {data_in};\n")
                                if write_en_port is not None:
                                    rtl_body += back_end.indent(f"end\n")
                            if data_out_port is not None and port_config.registered_input:
                                rtl_body += back_end.indent(f"{addr_name} <= {addr};\n")
                            if data_out_port is not None and port_config.registered_output:
                                if port_config.mem_ratio == 1:
                                    rtl_body += back_end.indent(f"{data_out} <= {memory_name}[{addr_name}];\n")
                                else:
                                    rtl_body += back_end.indent(f"{data_out} <= {memory_name}[{addr_name} / {port_config.mem_ratio}][{addr_name} % {port_config.mem_ratio}];\n")
                        if clk_en_port is not None:
                            rtl_body += back_end.indent(f"end\n")
                rtl_body += f"end\n"

            if data_in_port is None and data_out_port is not None and not port_config.registered_input:
                if port_config.registered_output:
                    rtl_body += f"always @(posedge {clk}) begin\n"
                    with back_end.indent_block():
                        if clk_en_port is not None:
                            rtl_body += back_end.indent(f"if ({clk_en}) begin\n")
                        with back_end.indent_block(clk_en_port is not None):
                            if port_config.mem_ratio == 1:
                                rtl_body += back_end.indent(f"{data_out} <= {memory_name}[{addr_name}];\n")
                            else:
                                rtl_body += back_end.indent(f"{data_out} <= {memory_name}[{addr_name} / {port_config.mem_ratio}][{addr_name} % {port_config.mem_ratio}];\n")
                        if clk_en_port is not None:
                            rtl_body += back_end.indent(f"end\n")
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
            self.optional_ports[f"{port_config.real_prefix}clk_en"] = (logic, Memory.INPUT)
            setattr(
                self,
                f"{port_config.real_prefix}clk",
                ClkPort(
                    auto_port_names = (
                        f"{port_config.real_prefix}clk",
                        f"{port_config.real_prefix}clock",
                        "clk",
                        "clock",
                        f"{port_config.real_prefix}clk_port",
                        f"{port_config.real_prefix}clock_port",
                        "clk_port",
                        "clock_port"
                    )
                )
            )

    def create_named_port_callback(self, name: str, net_type: Optional['NetType'] = None) -> Optional[Port]:
        """
        Called from the framework when unknown ports are accessed. This allows for dynamic port creation, though the default is to do nothing.
        Port creation should be as restrictive as possible and for any non-supported name, return None.
        This allows for regular attribute creation for non-port attributes.
        NOTE: create_named_port_callback should return the created port object instead of directly adding it to self
        """
        if name in self.optional_ports:
            if net_type is not None and net_type is not self.optional_ports[name][0]:
                raise SyntaxErrorException("Net type '{net_type}' is not valid for optional port '{name}'")
            if self.optional_ports[name][1] == Memory.INPUT:
                return Input(self.optional_ports[name][0])
            elif self.optional_ports[name][1] == Memory.OUTPUT:
                return Output(self.optional_ports[name][0])
            else:
                assert False
        raise InvalidPortError()

    def get_port_count(self) -> int:
        return len(self.config.port_configs)

    def body(self):
        from copy import deepcopy
        # Replace all data types with their equivalent number types
        mem_config = deepcopy(self.config)
        for port_config in mem_config.port_configs:
            port_config.data_type = Unsigned(port_config.data_type.get_num_bits()) if port_config.data_type is not None else None
        real_mem = _Memory(mem_config)
        # Hook up all of our ports to the internal one
        for port_name, port in self.get_inputs().items():
            if port_name.endswith("data_in"):
                port = explicit_adapt(port, Unsigned(length=port.get_num_bits()))
            mem_port = getattr(real_mem, port_name)
            mem_port <<= port
            #setattr(real_mem, port_name, port)
        for port_name, port in self.get_outputs().items():
            if port_name.endswith("data_out"):
                port <<= explicit_adapt(getattr(real_mem, port_name), port.get_net_type())
            else:
                port <<= getattr(real_mem, port_name)
        # clean up namespace
        del port
        del mem_port

class SimpleDualPortMemory(Memory):
    READ_PORT = 1
    WRITE_PORT = 0

    def construct(
        self,
        addr_type: NetType,
        data_type: NetType,
        registered_input_a: bool = True,
        registered_output_a: bool = False,
        registered_input_b: bool = True,
        registered_output_b: bool = False,
        init_content: Optional[Union[str, Callable]] = None
    ):
        config = MemoryConfig(
            (MemoryPortConfig(
                addr_type = addr_type,
                data_type = data_type,
                registered_input = registered_input_a,
                registered_output = registered_output_a
            ),
            MemoryPortConfig(
                addr_type = addr_type,
                data_type = data_type,
                registered_input = registered_input_b,
                registered_output = registered_output_b
            ),),
            init_content = init_content
        )
        return super().construct(config)
    def _get_prefix_for_port(self, default_idx: int, port: Optional[str] = None) -> str:
        if port == None:
            return self.config.port_configs[default_idx].real_prefix
        else:
            for p in self.config.port_configs:
                if p.prefix == port:
                    return p.real_prefix
        raise SyntaxErrorException(f"Port {port} is not valid for this memory instance")

    def read(self, addr: Junction, port: Optional[str] = None) -> Junction:
        """
        Creates a read binding for a given port. If no port is given, port 1 is used
        """
        prefix = self._get_prefix_for_port(self.READ_PORT, port)
        self.get_ports()[f"{prefix}addr"] <<= addr
        return self.get_ports()[f"{prefix}data_out"]
    def write(self, addr: Junction, data: Junction, write_en: Junction, port: Optional[str] = None) -> None:
        """
        Creates a read binding for a given port. If no port is given, port 0 is used
        """
        prefix = self._get_prefix_for_port(self.WRITE_PORT, port)
        self.get_ports()[f"{prefix}addr"] <<= addr
        self.get_ports()[f"{prefix}data_in"] <<= data
        self.get_ports()[f"{prefix}write_en"] <<= write_en
    def read_write(self, addr: Junction, data: Junction, write_en: Junction, port: Optional[str] = None) -> Junction:
        """
        Creates a read/write binding for a given port. If no port is given, port 0 is used
        """
        prefix = self._get_prefix_for_port(0, port)
        self.get_ports()[f"{prefix}addr"] <<= addr
        self.get_ports()[f"{prefix}data_in"] <<= data
        self.get_ports()[f"{prefix}write_en"] <<= write_en
        return self.get_ports()[f"{prefix}data_out"]

"""

Altera describes the inter-port read-write behavior the best: https://www.intel.com/programmable/technical-pdfs/654378.pdf, page 42.
They claim that you either get the old data (and in that case you *must* use the same clock on both ports) or you don't care.
This means that my current behavior in simulation is compliant with what Altera can do.

Altera/Xilinx read-old-data inference:

    always @ (posedge clk) begin
        if (we)
            mem[write_address] <= d;
        q <= mem[read_address];
    end

Altera read-new-data inference:

    always @ (posedge clk) begin
        if (we)
            mem[write_address] = d;
        q = mem[read_address]; // q does get d in this clock cycle if we is high
    end

Xilinx read-new-data inference:
    always @(posedge clk) begin
        if (we) begin
            RAM[addr] <= di;
            dout <= di;
        end else
            dout <= RAM[addr];
        end
    end
    ------------------
    always @(posedge clkB) begin
        if (weB)
            RAM[addrB] = diB;
        readB = RAM[addrB] ;
    end

    always @(posedge clkA) begin : portA
        if (weA)
            RAM[addrA] = diA;
        readA = RAM[addrA];
    end

    assign doA = readA;
    assign doB = readB;

NOTE: difference is only in <= v.s. = operators.

Altera doesn't suggest this:

    reg [7:0] mem [127:0];
    reg [6:0] read_address_reg;

    always @ (posedge clk) begin
        if (we)
            mem[write_address] <= d;
        read_address_reg <= read_address;
    end
    assign q = mem[read_address_reg];

Says, this is not clear if data is old or new. Just for fun, this *is* what I generate. Synplify pro apparently likes this style for dual-port memories.

Synplify pro write-first example:

always @(posedge clk) begin
    if (en) begin
        if (we) begin
            RAM[addr] <= di;
            dou <= di;
        end else
            dou <= RAM[addr];
        end
    end

always @(posedge clk)
    if (en & we) RAM[addr] <= di;

Synplify pro read-first example:

always@(posedge clk)
    if(rst == 1)
        data_out <= 0;
    else begin
        if(en) begin
            data_out <= mem[addr];
        end
    end

always @(posedge clk)
    if (en & we) mem[addr] <= data_in;

================================================
Microchip (Lattice) has a relatively decent in-depth paper on memory timings:

https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/ProductBrief/AC374_Read-Write+Operations+in+Dual-Port+SRAM+for+Flash-Based+cSoCs+and+FPGAs.pdf

Here they say that reads happen on the rising edge of the clock and writes on the falling edge.
They also say though that the write-enable signals are asserted while clock is high, so it's possible that they refer to the latching
edge as opposed to the capture edge. This is in contrast though with their claim that the flow-through data doesn't change when the other
port writes. They are very clear though: even flow-through data is edge-captured.

So, what they seem to be saying is:
- If a port writes, the data on its read port will be the data written.



Xilinx has another decent description: https://docs.xilinx.com/r/en-US/am007-versal-memory/Read-Operation?tocId=E7AyV9qShOdfqivIFnq8hQ

Here they say that without pipeline registers:
- Read address is registered on the read port and data is loaded into the output latch
- Write address is registered and data is written to memory. Read data is 'holding' the previous value???

There's also a diagram about the pipeline registers a little further down. They claim, they can selectively register:
- ADDR, EN, BWE, RDb_WR on the input
- DIN on the input
- DOUT *twice* potentially on the output

There's a diagram showing that even with all pipeline registers off, the output is still one cycle delayed (that is, registered) inside
the array. This is for UltraRAMs BTW...

It also shows that cell content changes on the rising edge of clock (same with DOUT).

For BRAMs, they have some waveforms here: https://docs.xilinx.com/r/en-US/am007-versal-memory/WRITE_FIRST-or-Transparent-Mode

This shows the output *NOT* registered.

This link shows: https://docs.xilinx.com/r/en-US/am007-versal-memory/Address-Collision something interesting:
In case of a write-first write on port A, a simultaneous read on port B results in X-es. In other words the only way to guarantee
ordering between ports is if:
- Write port is read-first mode.
- Read port is in whatever mode.

They show the following block-diagram:
https://docs.xilinx.com/r/en-US/am007-versal-memory/Optional-Output-Registers?tocId=2emHhSSsphiR8E~JhZJhcg

According to that, they truly can generate either sequence of read-after-write or write-after-read strobes.
They always have input registers and have an optional output register.

For Altera, apparently memories differ. The underlying block sometimes uses different edges for reads and writes (MLAB, M512, M4k),
some sometimes the same edge (M9k and above, also MLABs for V-series). Even when different edges are used, write data is latched
on the rising edge, but written on the falling one. In their table, they also claim that the only way cross-port read-write collisions
result in reliable output is if old data output is requested.

For me, old data output means registered input...
In those cases, cross input reads indeed give old data back, so that's good.
In fact, the only case when I violate expectations is when both ports are in new data mode.

So, my model actually matches at least Xilinx and Altera expectations. It's unclear what Microchip is doing...

"""