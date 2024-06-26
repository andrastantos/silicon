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
	logic [7:0] u_output_port_data;
	logic u6_output_port;
	logic u_out_reg_en;
	logic u_output_port_valid;
	logic u11_output_port;
	logic u12_output_port;
	logic u13_output_port;
	logic u14_output_port;
	logic [7:0] u1_output_port_data;
	logic u1_out_reg_en;
	logic u1_output_port_valid;
	logic u_output_port_ready;
	logic [7:0] u2_output_port_data;
	logic u2_out_reg_en;
	logic u2_output_port_valid;
	logic u1_output_port_ready;
	logic [7:0] u3_output_port_data;
	logic u3_out_reg_en;
	logic u3_output_port_valid;
	logic u2_output_port_ready;
	logic [7:0] intermediate_data;
	logic u4_out_reg_en;
	logic intermediate_valid;
	logic u3_output_port_ready;

	ForwardBuf u (
		.input_port_data(input_port_data),
		.input_port_ready(input_port_ready),
		.input_port_valid(input_port_valid),

		.output_port_data(u_output_port_data),
		.output_port_ready(u_output_port_ready),
		.output_port_valid(u_output_port_valid),

		.clock_port(clock_port),
		.reset_port(reset_port),
		.out_reg_en(u_out_reg_en),
		.clear(u6_output_port)
	);

	ForwardBuf_2 u1 (
		.input_port_data(u_output_port_data),
		.input_port_ready(u_output_port_ready),
		.input_port_valid(u_output_port_valid),

		.output_port_data(u1_output_port_data),
		.output_port_ready(u1_output_port_ready),
		.output_port_valid(u1_output_port_valid),

		.clock_port(clock_port),
		.reset_port(reset_port),
		.out_reg_en(u1_out_reg_en),
		.clear(u11_output_port)
	);

	ForwardBuf_3 u2 (
		.input_port_data(u1_output_port_data),
		.input_port_ready(u1_output_port_ready),
		.input_port_valid(u1_output_port_valid),

		.output_port_data(u2_output_port_data),
		.output_port_ready(u2_output_port_ready),
		.output_port_valid(u2_output_port_valid),

		.clock_port(clock_port),
		.reset_port(reset_port),
		.out_reg_en(u2_out_reg_en),
		.clear(u12_output_port)
	);

	ForwardBuf_4 u3 (
		.input_port_data(u2_output_port_data),
		.input_port_ready(u2_output_port_ready),
		.input_port_valid(u2_output_port_valid),

		.output_port_data(u3_output_port_data),
		.output_port_ready(u3_output_port_ready),
		.output_port_valid(u3_output_port_valid),

		.clock_port(clock_port),
		.reset_port(reset_port),
		.out_reg_en(u3_out_reg_en),
		.clear(u13_output_port)
	);

	ForwardBuf_5 u4 (
		.input_port_data(u3_output_port_data),
		.input_port_ready(u3_output_port_ready),
		.input_port_valid(u3_output_port_valid),

		.output_port_data(intermediate_data),
		.output_port_ready(output_port_ready),
		.output_port_valid(intermediate_valid),

		.clock_port(clock_port),
		.reset_port(reset_port),
		.out_reg_en(u4_out_reg_en),
		.clear(u14_output_port)
	);

	assign intermediate_ready = output_port_ready;
	assign u6_output_port = 1'h0;
	assign u11_output_port = 1'h0;
	assign u12_output_port = 1'h0;
	assign u13_output_port = 1'h0;
	assign u14_output_port = 1'h0;
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
	input logic reset_port,
	output logic out_reg_en,
	input logic clear
);

	logic [7:0] buf_data_data;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 8'h0 : out_reg_en ? input_port_data : buf_data_data;

	ForwardBufLogic_5 fsm (
		.clock_port(clock_port),
		.reset_port(reset_port),
		.input_valid(input_port_valid),
		.input_ready(input_port_ready),
		.output_valid(output_port_valid),
		.output_ready(output_port_ready),
		.out_reg_en(out_reg_en),
		.clear(clear)
	);

	assign output_port_data = buf_data_data;
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
	input logic reset_port,
	output logic out_reg_en,
	input logic clear
);

	logic [7:0] buf_data_data;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 8'h0 : out_reg_en ? input_port_data : buf_data_data;

	ForwardBufLogic_4 fsm (
		.clock_port(clock_port),
		.reset_port(reset_port),
		.input_valid(input_port_valid),
		.input_ready(input_port_ready),
		.output_valid(output_port_valid),
		.output_ready(output_port_ready),
		.out_reg_en(out_reg_en),
		.clear(clear)
	);

	assign output_port_data = buf_data_data;
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
	input logic reset_port,
	output logic out_reg_en,
	input logic clear
);

	logic [7:0] buf_data_data;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 8'h0 : out_reg_en ? input_port_data : buf_data_data;

	ForwardBufLogic_3 fsm (
		.clock_port(clock_port),
		.reset_port(reset_port),
		.input_valid(input_port_valid),
		.input_ready(input_port_ready),
		.output_valid(output_port_valid),
		.output_ready(output_port_ready),
		.out_reg_en(out_reg_en),
		.clear(clear)
	);

	assign output_port_data = buf_data_data;
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
	input logic reset_port,
	output logic out_reg_en,
	input logic clear
);

	logic [7:0] buf_data_data;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 8'h0 : out_reg_en ? input_port_data : buf_data_data;

	ForwardBufLogic_2 fsm (
		.clock_port(clock_port),
		.reset_port(reset_port),
		.input_valid(input_port_valid),
		.input_ready(input_port_ready),
		.output_valid(output_port_valid),
		.output_ready(output_port_ready),
		.out_reg_en(out_reg_en),
		.clear(clear)
	);

	assign output_port_data = buf_data_data;
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
	input logic reset_port,
	output logic out_reg_en,
	input logic clear
);

	logic [7:0] buf_data_data;

	always_ff @(posedge clock_port) buf_data_data <= reset_port ? 8'h0 : out_reg_en ? input_port_data : buf_data_data;

	ForwardBufLogic fsm (
		.clock_port(clock_port),
		.reset_port(reset_port),
		.input_valid(input_port_valid),
		.input_ready(input_port_ready),
		.output_valid(output_port_valid),
		.output_ready(output_port_ready),
		.out_reg_en(out_reg_en),
		.clear(clear)
	);

	assign output_port_data = buf_data_data;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ForwardBufLogic_5
////////////////////////////////////////////////////////////////////////////////
module ForwardBufLogic_5 (
	input logic clock_port,
	input logic reset_port,
	input logic input_valid,
	output logic input_ready,
	output logic output_valid,
	input logic output_ready,
	output logic out_reg_en,
	input logic clear
);

	logic buf_valid;

	assign out_reg_en = input_valid & input_ready;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : clear ? 1'h0 : (input_valid & input_ready) ? 1'h1 : (output_ready & buf_valid) ? 1'h0 : buf_valid;
	assign input_ready =  ~ buf_valid | output_ready;

	assign output_valid = buf_valid;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ForwardBufLogic_4
////////////////////////////////////////////////////////////////////////////////
module ForwardBufLogic_4 (
	input logic clock_port,
	input logic reset_port,
	input logic input_valid,
	output logic input_ready,
	output logic output_valid,
	input logic output_ready,
	output logic out_reg_en,
	input logic clear
);

	logic buf_valid;

	assign out_reg_en = input_valid & input_ready;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : clear ? 1'h0 : (input_valid & input_ready) ? 1'h1 : (output_ready & buf_valid) ? 1'h0 : buf_valid;
	assign input_ready =  ~ buf_valid | output_ready;

	assign output_valid = buf_valid;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ForwardBufLogic_3
////////////////////////////////////////////////////////////////////////////////
module ForwardBufLogic_3 (
	input logic clock_port,
	input logic reset_port,
	input logic input_valid,
	output logic input_ready,
	output logic output_valid,
	input logic output_ready,
	output logic out_reg_en,
	input logic clear
);

	logic buf_valid;

	assign out_reg_en = input_valid & input_ready;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : clear ? 1'h0 : (input_valid & input_ready) ? 1'h1 : (output_ready & buf_valid) ? 1'h0 : buf_valid;
	assign input_ready =  ~ buf_valid | output_ready;

	assign output_valid = buf_valid;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ForwardBufLogic_2
////////////////////////////////////////////////////////////////////////////////
module ForwardBufLogic_2 (
	input logic clock_port,
	input logic reset_port,
	input logic input_valid,
	output logic input_ready,
	output logic output_valid,
	input logic output_ready,
	output logic out_reg_en,
	input logic clear
);

	logic buf_valid;

	assign out_reg_en = input_valid & input_ready;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : clear ? 1'h0 : (input_valid & input_ready) ? 1'h1 : (output_ready & buf_valid) ? 1'h0 : buf_valid;
	assign input_ready =  ~ buf_valid | output_ready;

	assign output_valid = buf_valid;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ForwardBufLogic
////////////////////////////////////////////////////////////////////////////////
module ForwardBufLogic (
	input logic clock_port,
	input logic reset_port,
	input logic input_valid,
	output logic input_ready,
	output logic output_valid,
	input logic output_ready,
	output logic out_reg_en,
	input logic clear
);

	logic buf_valid;

	assign out_reg_en = input_valid & input_ready;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : clear ? 1'h0 : (input_valid & input_ready) ? 1'h1 : (output_ready & buf_valid) ? 1'h0 : buf_valid;
	assign input_ready =  ~ buf_valid | output_ready;

	assign output_valid = buf_valid;
endmodule


