////////////////////////////////////////////////////////////////////////////////
// AlphaBender
////////////////////////////////////////////////////////////////////////////////
module AlphaBender (
	input logic [7:0] in1_r,
	input logic [7:0] in1_g,
	input logic [7:0] in1_b,

	input logic [7:0] in2_r,
	input logic [7:0] in2_g,
	input logic [7:0] in2_b,

	input logic [7:0] alpha,
	output logic [7:0] outp_r,
	output logic [7:0] outp_g,
	output logic [7:0] outp_b
);

	logic [16:0] u8_output_port;
	logic [16:0] u18_output_port;
	logic [16:0] u28_output_port;

	assign outp_r = u8_output_port[15:8];
	assign outp_g = u18_output_port[15:8];
	assign outp_b = u28_output_port[15:8];

	assign u8_output_port = in1_r * alpha + in2_r * (8'hff - alpha) + 8'hff - 1'h1;
	assign u18_output_port = in1_g * alpha + in2_g * (8'hff - alpha) + 8'hff - 1'h1;
	assign u28_output_port = in1_b * alpha + in2_b * (8'hff - alpha) + 8'hff - 1'h1;
endmodule


