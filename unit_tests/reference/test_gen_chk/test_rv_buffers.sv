////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic clk,
	input logic rst
);

	logic data_valid;
	logic [7:0] data_data;
	logic data_ready;

	Generator u (
		.output_port_data(data_data),
		.output_port_ready(data_ready),
		.output_port_valid(data_valid),

		.clock_port(clk),
		.reset_port(rst)
	);

	Checker u1 (
		.input_port_data(data_data),
		.input_port_ready(data_ready),
		.input_port_valid(data_valid),

		.clock_port(clk),
		.reset_port(rst)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// Checker
////////////////////////////////////////////////////////////////////////////////
module Checker (
	input logic [7:0] input_port_data,
	output logic input_port_ready,
	input logic input_port_valid,

	input logic clock_port,
	input logic reset_port
);

	logic [7:0] data_members_data;
	logic [7:0] last_val;

	assign data_members_data = input_port_data;
	assign input_port_ready = 1'hx;
	assign last_val = 8'hx;
endmodule


////////////////////////////////////////////////////////////////////////////////
// Generator
////////////////////////////////////////////////////////////////////////////////
module Generator (
	output logic [7:0] output_port_data,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port
);

	logic [7:0] data_members_data;

	assign output_port_valid = 1'hx;
	assign output_port_data = 8'hx;
	assign data_members_data = 8'hx;
endmodule

