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

from .module import GenericModule
from .port import Input, Output, Wire, AutoInput, Port
from .net_type import NetType
from collections import OrderedDict
from dataclasses import dataclass
from .composite import Struct
from .utils import str_block, is_power_of_two
from .exceptions import SyntaxErrorException
from typing import Optional 
from .number import logic

@dataclass
class MemoryPortConfig:
    addr_type: NetType
    data_type: NetType
    registered_input: bool = True
    registered_output: bool = False
    prefix: Optional[str] = None

@dataclass
class MemoryConfig:
    port_a: MemoryPortConfig
    port_b: Optional[MemoryPortConfig]
    reset_content: Optional[str] = None

# TODO:
# - Add read-enable port
# - Add reset option for registers
# - Add byte-enables
class Memory(GenericModule):
    INPUT = 1
    OUTPUT = 2
    def construct(self, config: MemoryConfig):
        from copy import deepcopy
        self.config = deepcopy(config)
        self.port_configs = []
        self.optional_ports = OrderedDict()
        self._port_cnt = 0
        for port_config in (self.config.port_a, self.config.port_b):
            if port_config is not None:
                self._port_cnt += 1
        for port_prefix, port_config in (("port_a", self.config.port_a), ("port_b", self.config.port_b)):
            if port_config is not None:
                if port_config.prefix is None:
                    if self.get_port_count() == 1:
                        port_config.prefix = ""
                    else:
                        port_config.prefix = port_prefix + "_"
                else:
                    port_config.prefix += "_"
                self.port_configs.append(port_config)
        for port_config in self.port_configs:
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
        return self._port_cnt

    def generate_single_port_memory(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        # Sing-port memory
        mem_port_config = self.port_configs[0]
        data_bits = mem_port_config.data_type.get_num_bits()
        addr_bits = mem_port_config.addr_type.get_num_bits()

        has_data_in = hasattr(self, f"{mem_port_config.prefix}data_in")
        has_data_out = hasattr(self, f"{mem_port_config.prefix}data_out")
        has_write_en = hasattr(self, f"{mem_port_config.prefix}write_en")

        if not has_data_in and not has_data_out:
            raise SyntaxErrorException(f"Memory has neither its read nor its write data connected. That's not a valid use of a memory")
        if not has_data_in and self.config.reset_content is None:
            raise SyntaxErrorException(f"For ROMs, reset_content must be specified")
        if has_write_en and not has_data_in:
            raise SyntaxErrorException("If a memory has a write-enable, it must have a corresponding data")
        if not mem_port_config.registered_input:
            raise SyntaxErrorException("Unregistered inputs are not supported with inferred memories")
        rtl_body =  f"\twire [{data_bits-1}:0] mem [{(1 << addr_bits)-1}:0];\n"
        if self.config.reset_content is not None:
            rtl_body += f"\tinitial begin\n"
            if callable(self.config.reset_content):
                generator = self.config.reset_content()
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
            
        if has_data_out:
            if mem_port_config.registered_input:
                rtl_body += f"\twire [{addr_bits-1}:0] addr_reg;\n"
                addr_name = "addr_reg"
            else:
                addr_name = f"{mem_port_config.prefix}addr"
        if has_data_in or has_data_out:
            rtl_body += f"\talways @(posedge {mem_port_config.prefix}clk) begin\n"
            if has_data_in:
                if has_write_en:
                    rtl_body += f"\t    if ({mem_port_config.prefix}write_en) begin\n"
                    rtl_body += f"\t        mem[{mem_port_config.prefix}addr] <= {mem_port_config.prefix}data_in;\n"
                    rtl_body += f"\t    end\n"
                else:
                    rtl_body += f"\t    mem[{mem_port_config.prefix}addr] <= {mem_port_config.prefix}data_in;\n"
            if has_data_out and mem_port_config.registered_input:
                rtl_body += f"\t    {addr_name} <= {mem_port_config.prefix}addr;\n"
            if has_data_out and mem_port_config.registered_output:
                rtl_body += f"\t    {mem_port_config.prefix}data_out <= mem[{addr_name}];\n"
            rtl_body += f"\tend\n"
        if has_data_out and not mem_port_config.registered_output:
            rtl_body += f"\t{mem_port_config.prefix}data_out <= mem[{addr_name}];\n"
        return rtl_body

    def generate(self, netlist: 'Netlist', back_end: 'BackEnd') -> str:
        rtl_header = self._impl.generate_module_header(back_end)

        # Go through the ports again and make sure they're compatible with the geometry
        if self.get_port_count() == 0:
            raise SyntaxErrorException(f"All memory instances must have at least one port")
        if self.get_port_count() == 1:
            rtl_body = self.generate_single_port_memory(netlist, back_end)
        elif self.get_port_count() == 2:
            # Determine memory size
            mem_size = 0
            mem_data_bits = 0
            narrower_port_prefix = None # used for dual-port meories.
            narrower_port_config = None # used for dual-port meories.
            wider_port_prefix = None # used for dual-port meories.
            wider_port_config = None # used for dual-port meories.
            mem_ratio = 1 # Ratio between the two port widths. Defaults to 1, gets overriden if they are of different size
            for port_config in self.port_configs:
                data_bits = port_config.data_type.get_num_bits()
                addr_bits = port_config.addr_type.get_num_bits()
                mem_size = max(mem_size, data_bits * (1 << addr_bits))
                mem_data_bits = max(data_bits, mem_data_bits)

            for port_prefix, port_config in (("port_a", self.config.port_a), ("port_b", self.config.port_b)):
                if port_config is not None:
                    data_bits = port_config.data_type.get_num_bits()
                    if mem_data_bits % data_bits != 0:
                        raise SyntaxErrorException(f"For multi-port memories, data sizes on all ports must be integer multiples of one another")
                    ratio = mem_data_bits // data_bits
                    if not is_power_of_two(ratio):
                        raise SyntaxErrorException(f"For multi-port memories, data size ratios must be powers of 2")
                    if ratio == 1 and wider_port_config is None:
                        wider_port_config = port_config
                        wider_port_prefix = port_prefix
                    else:
                        mem_ratio = ratio
                        narrower_port_config = port_config
                        narrower_port_prefix = port_prefix
                    addr_bits = port_config.addr_type.get_num_bits()
                    port_mem_size = data_bits * addr_bits
            mem_addr_range = mem_size // mem_data_bits

            if not mem_port_config.registered_input and mem_port_config.registered_output:
                if mem_ratio == 1:
                    rtl_body =  f"\t    reg [{narrower_port_config.data_type.get_num_bits()-1}:0] ram[0:{mem_addr_range-1}];\n"
                    rtl_body += f"\t\n"
                    rtl_body += f"\t    reg [{narrower_port_config.data_type.get_num_bits()-1}:0] {narrower_port_prefix}_data_reg;\n"
                    rtl_body += f"\t    reg [{wider_port_config.data_type.get_num_bits()-1}:0] {wider_port_prefix}_data_reg;\n"
                    rtl_body += f"\t\n"
                    rtl_body += f"\t    always@(posedge {narrower_port_prefix}_clk)\n"
                    rtl_body += f"\t    begin\n"
                    rtl_body += f"\t        if({narrower_port_prefix}_write_en) begin\n"
                    rtl_body += f"\t            ram[{narrower_port_prefix}_addr] <= {narrower_port_prefix}_data_in;\n"
                    rtl_body += f"\t            {narrower_port_prefix}_data_reg <= {narrower_port_prefix}_data_in;\n"
                    rtl_body += f"\t        end else begin\n"
                    rtl_body += f"\t            {narrower_port_prefix}_data_reg <= ram[{narrower_port_prefix}_addr];\n"
                    rtl_body += f"\t        end\n"
                    rtl_body += f"\t    end\n"
                    rtl_body += f"\t    assign {narrower_port_prefix}_data_out = {narrower_port_prefix}_data_reg;\n"
                    rtl_body += f"\t\n"
                    rtl_body += f"\t    always@(posedge {wider_port_prefix}_clk)\n"
                    rtl_body += f"\t    begin\n"
                    rtl_body += f"\t        if({wider_port_prefix}_writen_en) begin\n"
                    rtl_body += f"\t            ram[{wider_port_prefix}_addr] <= {wider_port_prefix}_data_in;\n"
                    rtl_body += f"\t            {wider_port_prefix}_data_reg <= {wider_port_prefix}_data_in;\n"
                    rtl_body += f"\t        end else begin\n"
                    rtl_body += f"\t            {wider_port_prefix}_data_reg <= ram[{wider_port_prefix}_addr];\n"
                    rtl_body += f"\t        end\n"
                    rtl_body += f"\t    end\n"
                    rtl_body += f"\t    assign {wider_port_prefix}_data_out = {wider_port_prefix}_data_reg;\n"
                else:
                    rtl_body =  f"\t    reg [{mem_ratio-1}:0] [{narrower_port_config.data_type.get_num_bits()-1}:0] ram[0:{mem_addr_range-1}];\n"
                    rtl_body += f"\t\n"
                    rtl_body += f"\t    reg [{narrower_port_config.data_type.get_num_bits()-1}:0] {narrower_port_prefix}_data_reg;\n"
                    rtl_body += f"\t    reg [{wider_port_config.data_type.get_num_bits()-1}:0] {wider_port_prefix}_data_reg;\n"
                    rtl_body += f"\t\n"
                    rtl_body += f"\t    // Narrower port\n"
                    rtl_body += f"\t    always@(posedge {narrower_port_prefix}_clk)\n"
                    rtl_body += f"\t    begin\n"
                    rtl_body += f"\t        if({narrower_port_prefix}_write_en) begin\n"
                    rtl_body += f"\t            ram[{narrower_port_prefix}_addr / {mem_ratio}][{narrower_port_prefix}_addr % {mem_ratio}] <= {narrower_port_prefix}_data_in;\n"
                    rtl_body += f"\t            {narrower_port_prefix}_data_reg <= {narrower_port_prefix}_data_in;\n"
                    rtl_body += f"\t        end else begin\n"
                    rtl_body += f"\t            {narrower_port_prefix}_data_reg <= ram[{narrower_port_prefix}_addr / {mem_ratio}][{narrower_port_prefix}_addr % {mem_ratio}];\n"
                    rtl_body += f"\t        end\n"
                    rtl_body += f"\t    end\n"
                    rtl_body += f"\t    assign {narrower_port_prefix}_data_out = {narrower_port_prefix}_data_reg;\n"
                    rtl_body += f"\t\n"
                    rtl_body += f"\t    // Wider port\n"
                    rtl_body += f"\t    always@(posedge {wider_port_prefix}_clk)\n"
                    rtl_body += f"\t    begin\n"
                    rtl_body += f"\t        if({wider_port_prefix}_writen_en) begin\n"
                    rtl_body += f"\t            ram[{wider_port_prefix}_addr] <= {wider_port_prefix}_data_in;\n"
                    rtl_body += f"\t            {wider_port_prefix}_data_reg <= {wider_port_prefix}_data_in;\n"
                    rtl_body += f"\t        end else begin\n"
                    rtl_body += f"\t            {wider_port_prefix}_data_reg <= ram[{wider_port_prefix}_addr];\n"
                    rtl_body += f"\t        end\n"
                    rtl_body += f"\t    end\n"
                    rtl_body += f"\t    assign {wider_port_prefix}_data_out = {wider_port_prefix}_data_reg;\n"
            else:
                assert False
        else:
            raise SyntaxErrorException(f"No more than two ports are supported on memory instances")

        ret_val = (
            str_block(rtl_header, "", "\n\n") +
            str_block(rtl_body, "", "\n") +
            "endmodule"
        )
        return ret_val

"""
// Quartus Prime SystemVerilog Template
//
// True Dual-Port RAM with single clock and different data width on the two ports and width new data on read during write on same port
//
// The first datawidth and the widths of the addresses are specified
// The second data width is equal to DATA_WIDTH1 * RATIO, where RATIO = (1 << (ADDRESS_WIDTH1 - ADDRESS_WIDTH2)
// RATIO must have value that is supported by the memory blocks in your target
// device.  Otherwise, no RAM will be inferred.  
//
// Read-during-write behavior returns old data for mixed ports and the new data on the same port
//
// This style of RAM can be used on certain devices, e.g. Stratix V, which do not support old data for read during write on same port

module mixed_width_true_dual_port_ram_new_rw
    #(parameter int
        DATA_WIDTH1 = 8,
        ADDRESS_WIDTH1 = 10,
        ADDRESS_WIDTH2 = 8)
(
        input [ADDRESS_WIDTH1-1:0] addr1,
        input [ADDRESS_WIDTH2-1:0] addr2,
        input [DATA_WIDTH1      -1:0] data_in1, 
        input [DATA_WIDTH1*(1<<(ADDRESS_WIDTH1 - ADDRESS_WIDTH2))-1:0] data_in2, 
        input we1, we2, clk,
        output reg [DATA_WIDTH1-1      :0] data_out1,
        output reg [DATA_WIDTH1*(1<<(ADDRESS_WIDTH1 - ADDRESS_WIDTH2))-1:0] data_out2);
    
    localparam RATIO = 1 << (ADDRESS_WIDTH1 - ADDRESS_WIDTH2); // valid values are 2,4,8... family dependent
    localparam DATA_WIDTH2 = DATA_WIDTH1 * RATIO;
    localparam RAM_DEPTH = 1 << ADDRESS_WIDTH2;

    // Use a multi-dimensional packed array to model the different read/ram width
    reg [RATIO-1:0] [DATA_WIDTH1-1:0] ram[0:RAM_DEPTH-1];
    
    reg [DATA_WIDTH1-1:0] data_reg1;
    reg [DATA_WIDTH2-1:0] data_reg2;

    // Port A
    always@(posedge clk)
    begin
        if(we1) 
        begin 
            ram[addr1 / RATIO][addr1 % RATIO] <= data_in1;
            data_reg1 <= data_in1;
        end
        else
        begin 
            data_reg1 <= ram[addr1 / RATIO][addr1 % RATIO];
        end
    end
    assign data_out1 = data_reg1;

    // port B
    always@(posedge clk)
    begin
        if(we2)
        begin
            ram[addr2] <= data_in2;
            data_reg2 <= data_in2;
        end
        else
        begin
            data_reg2 <= ram[addr2];
        end
    end
    
    assign data_out2 = data_reg2;
endmodule : mixed_width_true_dual_port_ram_new_rw
"""