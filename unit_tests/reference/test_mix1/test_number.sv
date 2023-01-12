////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic [4:0] in_a,
	input logic [15:0] in_b,
	input logic [15:0] in_c,
	output logic [15:0] out_num,
	output logic signed [15:0] out_num_b,
	output logic out_a,
	output logic [10:0] out_b,
	output logic [4:0] out_c,
	output logic [10:0] out_d
);

	logic c0;
	logic u5_out_a;

	assign out_num = in_b & in_c;
	assign out_c = {in_a[0], in_b[0], c0, c0, in_b[0]};
	assign out_b = {6'(1'h0), u5_out_a, in_a[2:0], c0};
	assign out_d = {7'(1'h1), 4'({c0, in_b[0], in_a[4]})};
	assign out_num_b = 5'h1f;

	test_number_and_gate u (
		.in_a(in_a[0]),
		.in_b(in_b[0]),
		.out_a(c0)
	);

	test_number_and_gate u5 (
		.in_a(in_a[3]),
		.in_b(in_a[4]),
		.out_a(u5_out_a)
	);

	assign out_a = 1'hx;
endmodule


////////////////////////////////////////////////////////////////////////////////
// test_number_and_gate
////////////////////////////////////////////////////////////////////////////////
module test_number_and_gate (
	input logic in_a,
	input logic in_b,
	output logic out_a
);
	assign out_a = in_a & in_b;
endmodule





