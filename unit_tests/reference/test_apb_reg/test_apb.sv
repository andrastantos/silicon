////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic clk,
	input logic rst,
	input logic apb_penable,
	output logic apb_pready,
	input logic apb_psel,
	input logic apb_pwrite,
	input logic [7:0] apb_pwdata,
	output logic [7:0] apb_prdata,
	input logic [7:0] apb_paddr,

	output logic bit0,
	input logic stat3
);

	logic reg1_write_strobe;
	logic reg1_read_strobe;
	logic [3:0] high_nibble;
	logic reg1_lsb_stat;

	APBReg reg1 (
		.clk(clk),
		.rst(rst),
		.write_strobe(reg1_write_strobe),
		.read_strobe(reg1_read_strobe),
		.apb_bus_penable(apb_penable),
		.apb_bus_pready(apb_pready),
		.apb_bus_psel(apb_psel),
		.apb_bus_pwrite(apb_pwrite),
		.apb_bus_pwdata(apb_pwdata),
		.apb_bus_prdata(apb_prdata),
		.apb_bus_paddr(apb_paddr),

		.HighNibble_ctrl(high_nibble),
		.lsb_stat(reg1_lsb_stat),
		.lsb_ctrl(bit0),
		.bit3_stat(stat3)
	);

	assign reg1_lsb_stat = high_nibble[0];
endmodule


////////////////////////////////////////////////////////////////////////////////
// APBReg
////////////////////////////////////////////////////////////////////////////////
module APBReg (
	input logic clk,
	input logic rst,
	output logic write_strobe,
	output logic read_strobe,
	input logic apb_bus_penable,
	output logic apb_bus_pready,
	input logic apb_bus_psel,
	input logic apb_bus_pwrite,
	input logic [7:0] apb_bus_pwdata,
	output logic [7:0] apb_bus_prdata,
	input logic [7:0] apb_bus_paddr,

	output logic [3:0] HighNibble_ctrl,
	input logic lsb_stat,
	output logic lsb_ctrl,
	input logic bit3_stat
);

	logic reg_decode;
	logic write_strobe_1;
	logic read_strobe_1;
	logic [7:0] read_value;

	assign reg_decode = apb_bus_paddr == 1'h0;
	assign write_strobe_1 = apb_bus_psel & apb_bus_pwrite & apb_bus_penable & reg_decode;
	assign read_strobe_1 = apb_bus_psel &  ~ apb_bus_pwrite & apb_bus_penable & reg_decode;
	always_ff @(posedge clk) HighNibble_ctrl <= rst ? 4'h0 : write_strobe_1 ? apb_bus_pwdata[7:4] : HighNibble_ctrl;
	always_ff @(posedge clk) lsb_ctrl <= rst ? 1'h0 : write_strobe_1 ? apb_bus_pwdata[0] : lsb_ctrl;
	assign read_value = {HighNibble_ctrl[3], HighNibble_ctrl[2], HighNibble_ctrl[1], HighNibble_ctrl[0], bit3_stat, 1'h0, 1'h0, lsb_stat};
	assign apb_bus_pready = 1'h1;

	assign write_strobe = write_strobe_1;
	assign read_strobe = read_strobe_1;
	assign apb_bus_prdata = read_value;
endmodule


