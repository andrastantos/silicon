////////////////////////////////////////////////////////////////////////////////
// AlphaBender
////////////////////////////////////////////////////////////////////////////////
module AlphaBender (
	input logic [11:0] in1_b,
	input logic [11:0] in1_g,
	input logic [11:0] in1_r,

	input logic [11:0] in2_b,
	input logic [11:0] in2_g,
	input logic [11:0] in2_r,

	input logic [7:0] alpha,
	output logic [11:0] outp_b,
	output logic [11:0] outp_g,
	output logic [11:0] outp_r
);

	logic [20:0] u5_output_port;
	logic [20:0] u13_output_port;
	logic [20:0] u21_output_port;

	assign outp_r = u5_output_port[19:8];
	assign outp_g = u13_output_port[19:8];
	assign outp_b = u21_output_port[19:8];

	assign u5_output_port = in1_r * alpha + 20'b0 + in2_r * (8'hff - alpha) + 20'b0 + 21'b0 + 7'h7f;
	assign u13_output_port = in1_g * alpha + 20'b0 + in2_g * (8'hff - alpha) + 20'b0 + 21'b0 + 7'h7f;
	assign u21_output_port = in1_b * alpha + 20'b0 + in2_b * (8'hff - alpha) + 20'b0 + 21'b0 + 7'h7f;
endmodule


