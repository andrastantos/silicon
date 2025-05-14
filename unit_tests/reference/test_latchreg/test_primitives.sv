////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic [7:0] in1,
	output logic [7:0] out1,
	input logic clk,
	input logic rst,
	input logic enable
);

	PosLatchReg dut (
		.output_port(out1),
		.input_port(in1),
		.clock_port(clk),
		.reset_port(rst),
		.enable(enable)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// PosLatchReg
////////////////////////////////////////////////////////////////////////////////
module PosLatchReg (
	output logic [7:0] output_port,
	input logic [7:0] input_port,
	input logic clock_port,
	input logic reset_port,
	input logic enable
);

	logic [7:0] r_output_port;

	always_ff @(posedge clock_port) r_output_port <= reset_port ? 8'h0 : enable ? input_port : r_output_port;
	assign output_port = enable ? input_port : r_output_port;

endmodule


