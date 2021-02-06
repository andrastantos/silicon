////////////////////////////////////////////////////////////////////////////////
// AlphaBender
////////////////////////////////////////////////////////////////////////////////
module AlphaBender (
	input logic [11:0] in1_r,
	input logic [11:0] in1_g,
	input logic [11:0] in1_b,

	input logic [11:0] in2_r,
	input logic [11:0] in2_g,
	input logic [11:0] in2_b,

	input logic [7:0] alpha,
	output logic [11:0] outp_r,
	output logic [11:0] outp_g,
	output logic [11:0] outp_b
);

	assign outp_r = (in1_r * alpha + in2_r * (8'hff - alpha) + 7'h7f)[19:8];
	assign outp_g = (in1_g * alpha + in2_g * (8'hff - alpha) + 7'h7f)[19:8];
	assign outp_b = (in1_b * alpha + in2_b * (8'hff - alpha) + 7'h7f)[19:8];

endmodule


