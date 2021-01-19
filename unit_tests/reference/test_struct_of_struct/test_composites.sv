////////////////////////////////////////////////////////////////////////////////
// AlphaBender
////////////////////////////////////////////////////////////////////////////////
module AlphaBender (
	input logic [7:0] in1_pixel_b,
	input logic [7:0] in1_pixel_g,
	input logic [7:0] in1_pixel_r,
	input logic in1_valid,

	input logic [7:0] in2_pixel_b,
	input logic [7:0] in2_pixel_g,
	input logic [7:0] in2_pixel_r,
	input logic in2_valid,

	input logic [7:0] alpha,
	output logic [7:0] outp_pixel_b,
	output logic [7:0] outp_pixel_g,
	output logic [7:0] outp_pixel_r,
	output logic outp_valid,

	output logic error
);

	assign outp_pixel_r = (in1_pixel_r * alpha + in2_pixel_r * (8'hff - alpha) + 7'h7f)[15:8];
	assign outp_pixel_g = (in1_pixel_g * alpha + in2_pixel_g * (8'hff - alpha) + 7'h7f)[15:8];
	assign outp_pixel_b = (in1_pixel_b * alpha + in2_pixel_b * (8'hff - alpha) + 7'h7f)[15:8];
	assign outp_valid = in1_valid & in2_valid;
	assign error = in1_valid ^ in2_valid;

endmodule


