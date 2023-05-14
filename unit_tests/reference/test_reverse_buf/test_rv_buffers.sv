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

	logic u2_output_port;

	ReverseBuf u (
		.input_port_data(in1_data),
		.input_port_ready(in1_ready),
		.input_port_valid(in1_valid),

		.output_port_data(out1_data),
		.output_port_ready(out1_ready),
		.output_port_valid(out1_valid),

		.clock_port(clk),
		.reset_port(rst),
		.clear(u2_output_port)
	);

	assign u2_output_port = 1'h0;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ReverseBuf
////////////////////////////////////////////////////////////////////////////////
module ReverseBuf (
	input logic [7:0] input_port_data,
	output logic input_port_ready,
	input logic input_port_valid,

	output logic [7:0] output_port_data,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port,
	input logic clear
);

	logic [7:0] buf_data_data;
	logic buf_load;
	logic buf_valid;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 8'h0 : buf_load ? input_port_data : buf_data_data;
	always_ff @(posedge clock_port) input_port_ready <= reset_port ? 1'h0 : output_port_ready;
	assign buf_load = input_port_valid & input_port_ready &  ~ output_port_ready;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : clear ? 1'h0 : output_port_ready ? 1'h0 : buf_load ? 1'h1 : buf_valid;
	assign output_port_valid = (output_port_ready &  ~ buf_valid) ? input_port_valid & input_port_ready : buf_valid;
	assign output_port_data = (output_port_ready &  ~ buf_valid) ? input_port_data : buf_data_data;

endmodule


