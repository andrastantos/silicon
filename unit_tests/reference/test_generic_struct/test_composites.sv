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

	logic [16:0] u7_output_port;
	logic [16:0] u17_output_port;
	logic [16:0] u27_output_port;

	assign outp_r = u7_output_port[15:8];
	assign outp_g = u17_output_port[15:8];
	assign outp_b = u27_output_port[15:8];

	assign u7_output_port = in1_r * alpha + 16'b0 + in2_r * (8'hff - alpha) + 16'b0 + 17'b0 + 8'hff - 1'h1;
	assign u17_output_port = in1_g * alpha + 16'b0 + in2_g * (8'hff - alpha) + 16'b0 + 17'b0 + 8'hff - 1'h1;
	assign u27_output_port = in1_b * alpha + 16'b0 + in2_b * (8'hff - alpha) + 16'b0 + 17'b0 + 8'hff - 1'h1;
endmodule


