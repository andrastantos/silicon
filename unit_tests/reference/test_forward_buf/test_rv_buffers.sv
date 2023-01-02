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

	ForwardBuf fb (
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

	logic fsm_out_reg_en;
	logic [7:0] buf_data_data;

	ForwardBufLogic fsm (
		.clock_port(clock_port),
		.reset_port(reset_port),
		.input_valid(input_port_valid),
		.input_ready(input_port_ready),
		.output_valid(output_port_valid),
		.output_ready(output_port_ready),
		.out_reg_en(fsm_out_reg_en)
	);

	RegEn u (
		.output_port_data(buf_data_data),

		.input_port_data(input_port_data),

		.clock_port(clock_port),
		.reset_port(reset_port),
		.clock_en(fsm_out_reg_en)
	);

	assign output_port_data = buf_data_data;
endmodule


////////////////////////////////////////////////////////////////////////////////
// RegEn
////////////////////////////////////////////////////////////////////////////////
module RegEn (
	output logic [7:0] output_port_data,
	input logic [7:0] input_port_data,
	input logic clock_port,
	input logic reset_port,
	input logic clock_en
);

	logic [7:0] value_data;

	always_ff @(posedge clock_port) value_data <= reset_port ? 8'h0 : clock_en ? input_port_data : value_data;

	assign output_port_data = value_data;
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
	output logic out_reg_en
);

	logic buf_valid;

	assign out_reg_en = input_valid & input_ready;
	always_ff @(posedge clock_port) buf_valid <= reset_port ? 1'h0 : (input_valid & input_ready) ? 1'h1 : (output_ready & buf_valid) ? 1'h0 : buf_valid;
	assign input_ready =  ~ buf_valid | output_ready;

	assign output_valid = buf_valid;
endmodule


