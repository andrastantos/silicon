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

	logic [16:0] u5_output_port;
	logic [16:0] u13_output_port;
	logic [16:0] u21_output_port;

	assign outp_pixel_r = u5_output_port[15:8];
	assign outp_pixel_g = u13_output_port[15:8];
	assign outp_pixel_b = u21_output_port[15:8];
	assign outp_valid = in1_valid & in2_valid;
	assign error = in1_valid ^ in2_valid;

	assign u5_output_port = in1_pixel_r * alpha + 16'b0 + in2_pixel_r * (8'hff - alpha) + 16'b0 + 17'b0 + 7'h7f;
	assign u13_output_port = in1_pixel_g * alpha + 16'b0 + in2_pixel_g * (8'hff - alpha) + 16'b0 + 17'b0 + 7'h7f;
	assign u21_output_port = in1_pixel_b * alpha + 16'b0 + in2_pixel_b * (8'hff - alpha) + 16'b0 + 17'b0 + 7'h7f;
endmodule


