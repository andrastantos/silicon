////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic [7:0] in1_r,
	input logic [7:0] in1_g,
	input logic [7:0] in1_b,

	output logic [7:0] outp_r,
	output logic [7:0] outp_g,
	output logic [7:0] outp_b
);

	Sub u (
		.in1_r(in1_r),
		.in1_g(in1_g),
		.in1_b(in1_b),

		.in2_r(in1_r),
		.in2_g(in1_g),
		.in2_b(in1_b),

		.outp_r(outp_r),
		.outp_g(outp_g),
		.outp_b(outp_b)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// Sub
////////////////////////////////////////////////////////////////////////////////
module Sub (
	input logic [7:0] in1_r,
	input logic [7:0] in1_g,
	input logic [7:0] in1_b,

	input logic [7:0] in2_r,
	input logic [7:0] in2_g,
	input logic [7:0] in2_b,

	output logic [7:0] outp_r,
	output logic [7:0] outp_g,
	output logic [7:0] outp_b
);

	assign outp_r = 1'h1 ? in1_r : in1_r;
	assign outp_g = 1'h1 ? in1_g : in1_g;
	assign outp_b = 1'h1 ? in1_b : in1_b;

endmodule


