////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic [7:0] in1_data,
	output logic in1_ready,
	input logic in1_valid,

	output logic [7:0] out1_data,
	input logic out1_ready,
	output logic out1_valid,

	input logic clk,
	input logic rst
);

	Pacer dut (
		.input_port_data(in1_data),
		.input_port_ready(in1_ready),
		.input_port_valid(in1_valid),

		.output_port_data(in1_data),
		.output_port_ready(out1_ready),
		.output_port_valid(out1_valid),

		.clock_port(clk),
		.reset_port(rst)
	);

	assign out1_data = in1_data;
endmodule


////////////////////////////////////////////////////////////////////////////////
// Pacer
////////////////////////////////////////////////////////////////////////////////
module Pacer (
	input logic [7:0] input_port_data,
	output logic input_port_ready,
	input logic input_port_valid,

	output logic [7:0] output_port_data,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port
);

	logic wait_done;
	logic transfer;
	logic [1:0] u10_output_port;
	logic [1:0] next_wait_cnt;
	logic [1:0] wait_cnt;

	assign wait_done = wait_cnt == 2'h2;
	assign input_port_ready = wait_done & output_port_ready;
	assign output_port_valid = wait_done & input_port_valid;
	assign transfer = input_port_valid & output_port_ready & wait_done;
	assign next_wait_cnt = transfer ? 1'h0 : u10_output_port;
	always_ff @(posedge clock_port) wait_cnt <= reset_port ? 2'h0 : next_wait_cnt;

	ExplicitAdaptor u10 (
		.input_port(wait_done ? 2'h2 : wait_cnt + 1'h1),
		.output_port(u10_output_port)
	);

	assign output_port_data = input_port_data;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ExplicitAdaptor
////////////////////////////////////////////////////////////////////////////////
module ExplicitAdaptor (
	input logic [1:0] input_port,
	output logic [1:0] output_port
);

	assign output_port = input_port;

endmodule


