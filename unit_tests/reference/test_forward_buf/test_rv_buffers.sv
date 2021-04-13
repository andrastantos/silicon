////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic [15:0] in1_data,
	input logic signed [12:0] in1_data2,
	output logic in1_ready,
	input logic in1_valid,

	output logic [15:0] out1_data,
	output logic signed [12:0] out1_data2,
	input logic out1_ready,
	output logic out1_valid,

	input logic clk,
	input logic rst
);

	ForwardBuf fb (
		.input_port_data(in1_data),
		.input_port_data2(in1_data2),
		.input_port_ready(in1_ready),
		.input_port_valid(in1_valid),

		.output_port_data(out1_data),
		.output_port_data2(out1_data2),
		.output_port_ready(out1_ready),
		.output_port_valid(out1_valid),

		.clock_port(clk),
		.reset_port(rst)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// ForwardBuf
////////////////////////////////////////////////////////////////////////////////
module ForwardBuf (
	input logic [15:0] input_port_data,
	input logic signed [12:0] input_port_data2,
	output logic input_port_ready,
	input logic input_port_valid,

	output logic [15:0] output_port_data,
	output logic signed [12:0] output_port_data2,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port
);

	logic [15:0] buf_data_data;
	logic signed [12:0] buf_data_data2;
	logic buf_valid;
	logic in_ready;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 16'h0 : (input_port_valid & in_ready) ? input_port_data : buf_data_data;
	always_ff @(posedge clock_port) buf_data_data2 <= reset_port ? 13'h0 : (input_port_valid & in_ready) ? input_port_data2 : buf_data_data2;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : (input_port_valid & in_ready) ? 1'h1 : (output_port_ready & buf_valid) ? 1'h0 : buf_valid;
	assign in_ready =  ~ buf_valid | output_port_ready;

	assign output_port_data = buf_data_data;
	assign output_port_data2 = buf_data_data2;
	assign output_port_valid = buf_valid;
	assign input_port_ready = in_ready;
endmodule


