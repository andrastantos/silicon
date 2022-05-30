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

	DelayLine dut (
		.input_port_data(in1_data),
		.input_port_ready(in1_ready),
		.input_port_valid(in1_valid),

		.output_port_data(out1_data),
		.output_port_ready(out1_ready),
		.output_port_valid(out1_valid),

		.clock_port(clk),
		.reset_port(rst)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// DelayLine
////////////////////////////////////////////////////////////////////////////////
module DelayLine (
	input logic [7:0] input_port_data,
	output logic input_port_ready,
	input logic input_port_valid,

	output logic [7:0] output_port_data,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port
);

	logic intermediate_ready;
	logic [7:0] u_output_port_data_data;
	logic u_output_port_valid_valid;
	logic [7:0] u1_output_port_data_data;
	logic u1_output_port_valid_valid;
	logic u_output_port_ready_ready;
	logic [7:0] u2_output_port_data_data;
	logic u2_output_port_valid_valid;
	logic u1_output_port_ready_ready;
	logic [7:0] u3_output_port_data_data;
	logic u3_output_port_valid_valid;
	logic u2_output_port_ready_ready;
	logic [7:0] intermediate_data;
	logic intermediate_valid;
	logic u3_output_port_ready_ready;

	ForwardBuf u (
		.input_port_data(input_port_data),
		.input_port_ready(input_port_ready),
		.input_port_valid(input_port_valid),

		.output_port_data(u_output_port_data_data),
		.output_port_ready(u_output_port_ready_ready),
		.output_port_valid(u_output_port_valid_valid),

		.clock_port(clock_port),
		.reset_port(reset_port)
	);

	ForwardBuf_2 u1 (
		.input_port_data(u_output_port_data_data),
		.input_port_ready(u_output_port_ready_ready),
		.input_port_valid(u_output_port_valid_valid),

		.output_port_data(u1_output_port_data_data),
		.output_port_ready(u1_output_port_ready_ready),
		.output_port_valid(u1_output_port_valid_valid),

		.clock_port(clock_port),
		.reset_port(reset_port)
	);

	ForwardBuf_3 u2 (
		.input_port_data(u1_output_port_data_data),
		.input_port_ready(u1_output_port_ready_ready),
		.input_port_valid(u1_output_port_valid_valid),

		.output_port_data(u2_output_port_data_data),
		.output_port_ready(u2_output_port_ready_ready),
		.output_port_valid(u2_output_port_valid_valid),

		.clock_port(clock_port),
		.reset_port(reset_port)
	);

	ForwardBuf_4 u3 (
		.input_port_data(u2_output_port_data_data),
		.input_port_ready(u2_output_port_ready_ready),
		.input_port_valid(u2_output_port_valid_valid),

		.output_port_data(u3_output_port_data_data),
		.output_port_ready(u3_output_port_ready_ready),
		.output_port_valid(u3_output_port_valid_valid),

		.clock_port(clock_port),
		.reset_port(reset_port)
	);

	ForwardBuf_5 u4 (
		.input_port_data(u3_output_port_data_data),
		.input_port_ready(u3_output_port_ready_ready),
		.input_port_valid(u3_output_port_valid_valid),

		.output_port_data(intermediate_data),
		.output_port_ready(output_port_ready),
		.output_port_valid(intermediate_valid),

		.clock_port(clock_port),
		.reset_port(reset_port)
	);

	assign intermediate_ready = output_port_ready;
	assign output_port_data = intermediate_data;
	assign output_port_valid = intermediate_valid;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ForwardBuf_5
////////////////////////////////////////////////////////////////////////////////
module ForwardBuf_5 (
	input logic [7:0] input_port_data,
	output logic input_port_ready,
	input logic input_port_valid,

	output logic [7:0] output_port_data,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port
);

	logic [7:0] buf_data_data;
	logic buf_valid;
	logic in_ready;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 8'h0 : (input_port_valid & in_ready) ? input_port_data : buf_data_data;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : (input_port_valid & in_ready) ? 1'h1 : (output_port_ready & buf_valid) ? 1'h0 : buf_valid;
	assign in_ready =  ~ buf_valid | output_port_ready;

	assign output_port_data = buf_data_data;
	assign output_port_valid = buf_valid;
	assign input_port_ready = in_ready;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ForwardBuf_4
////////////////////////////////////////////////////////////////////////////////
module ForwardBuf_4 (
	input logic [7:0] input_port_data,
	output logic input_port_ready,
	input logic input_port_valid,

	output logic [7:0] output_port_data,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port
);

	logic [7:0] buf_data_data;
	logic buf_valid;
	logic in_ready;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 8'h0 : (input_port_valid & in_ready) ? input_port_data : buf_data_data;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : (input_port_valid & in_ready) ? 1'h1 : (output_port_ready & buf_valid) ? 1'h0 : buf_valid;
	assign in_ready =  ~ buf_valid | output_port_ready;

	assign output_port_data = buf_data_data;
	assign output_port_valid = buf_valid;
	assign input_port_ready = in_ready;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ForwardBuf_3
////////////////////////////////////////////////////////////////////////////////
module ForwardBuf_3 (
	input logic [7:0] input_port_data,
	output logic input_port_ready,
	input logic input_port_valid,

	output logic [7:0] output_port_data,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port
);

	logic [7:0] buf_data_data;
	logic buf_valid;
	logic in_ready;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 8'h0 : (input_port_valid & in_ready) ? input_port_data : buf_data_data;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : (input_port_valid & in_ready) ? 1'h1 : (output_port_ready & buf_valid) ? 1'h0 : buf_valid;
	assign in_ready =  ~ buf_valid | output_port_ready;

	assign output_port_data = buf_data_data;
	assign output_port_valid = buf_valid;
	assign input_port_ready = in_ready;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ForwardBuf_2
////////////////////////////////////////////////////////////////////////////////
module ForwardBuf_2 (
	input logic [7:0] input_port_data,
	output logic input_port_ready,
	input logic input_port_valid,

	output logic [7:0] output_port_data,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port
);

	logic [7:0] buf_data_data;
	logic buf_valid;
	logic in_ready;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 8'h0 : (input_port_valid & in_ready) ? input_port_data : buf_data_data;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : (input_port_valid & in_ready) ? 1'h1 : (output_port_ready & buf_valid) ? 1'h0 : buf_valid;
	assign in_ready =  ~ buf_valid | output_port_ready;

	assign output_port_data = buf_data_data;
	assign output_port_valid = buf_valid;
	assign input_port_ready = in_ready;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ForwardBuf
////////////////////////////////////////////////////////////////////////////////
module ForwardBuf (
	input logic [7:0] input_port_data,
	output logic input_port_ready,
	input logic input_port_valid,

	output logic [7:0] output_port_data,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port
);

	logic [7:0] buf_data_data;
	logic buf_valid;
	logic in_ready;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 8'h0 : (input_port_valid & in_ready) ? input_port_data : buf_data_data;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : (input_port_valid & in_ready) ? 1'h1 : (output_port_ready & buf_valid) ? 1'h0 : buf_valid;
	assign in_ready =  ~ buf_valid | output_port_ready;

	assign output_port_data = buf_data_data;
	assign output_port_valid = buf_valid;
	assign input_port_ready = in_ready;
endmodule


