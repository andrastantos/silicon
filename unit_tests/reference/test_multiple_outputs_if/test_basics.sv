////////////////////////////////////////////////////////////////////////////////
// Outer
////////////////////////////////////////////////////////////////////////////////
module Outer (
);

	logic wire1_r1;
	logic wire1_r2;
	logic wire2_r1;
	logic wire2_r2;
	logic wire1_n1;
	logic wire1_n2;
	logic wire2_n1;
	logic wire2_n2;

	Inner1 inner1 (
		.inner1_in_n1(1'hx),
		.inner1_in_n2(1'hx),

		.inner1_out1_n1(wire1_n1),
		.inner1_out1_n2(wire1_n2),
		.inner1_out1_r1(1'hx),
		.inner1_out1_r2(1'hx),

		.inner1_out2_n1(wire2_n1),
		.inner1_out2_n2(wire2_n2),
		.inner1_out2_r1(1'hx),
		.inner1_out2_r2(1'hx)
	);

	assign wire1_r1 = 1'hx;
	assign wire1_r2 = 1'hx;
	assign wire2_r1 = 1'hx;
	assign wire2_r2 = 1'hx;
endmodule


////////////////////////////////////////////////////////////////////////////////
// Inner1
////////////////////////////////////////////////////////////////////////////////
module Inner1 (
	input logic inner1_in_n1,
	input logic inner1_in_n2,
	output logic inner1_in_r1,
	output logic inner1_in_r2,

	output logic inner1_out1_n1,
	output logic inner1_out1_n2,
	input logic inner1_out1_r1,
	input logic inner1_out1_r2,

	output logic inner1_out2_n1,
	output logic inner1_out2_n2,
	input logic inner1_out2_r1,
	input logic inner1_out2_r2
);

	assign inner1_out2_n1 = inner1_out1_n1;
	assign inner1_out2_n2 = inner1_out1_n2;

	Inner2 inner2 (
		.inner2_out_n1(inner1_out1_n1),
		.inner2_out_n2(inner1_out1_n2),
		.inner2_out_r1(inner1_out2_r1),
		.inner2_out_r2(inner1_out2_r2)
	);

	assign inner1_in_r1 = 1'hx;
	assign inner1_in_r2 = 1'hx;
endmodule


////////////////////////////////////////////////////////////////////////////////
// Inner2
////////////////////////////////////////////////////////////////////////////////
module Inner2 (
	output logic inner2_out_n1,
	output logic inner2_out_n2,
	input logic inner2_out_r1,
	input logic inner2_out_r2
);

	assign inner2_out_n1 = 1'h1;
	assign inner2_out_n2 = 1'h1;

endmodule


