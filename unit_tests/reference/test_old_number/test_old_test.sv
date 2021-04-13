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
	output logic [2:0] out_c,
	output logic [10:0] out_d
);

	logic a0;
	logic b0;
	logic c0;
	logic u9_out_a;

	assign a0 = in_a[0];
	assign b0 = in_b[0];
	assign out_num = in_b & in_c;
	assign out_num_b = 5'h1f;
	assign out_b = {6'(1'h0), u9_out_a, in_a[3:1], c0};
	assign out_d = {7'(1'h0), 4'({c0, b0, in_a[4]})};

	and_gate u7 (
		.in_a(a0),
		.in_b(b0),
		.out_a(c0)
	);

	and_gate u9 (
		.in_a(in_a[3]),
		.in_b(in_a[4]),
		.out_a(u9_out_a)
	);

	assign out_a = 1'hx;
	assign out_c = 3'hx;
endmodule


////////////////////////////////////////////////////////////////////////////////
// and_gate
////////////////////////////////////////////////////////////////////////////////
module and_gate (
	input logic in_a,
	input logic in_b,
	output logic out_a
);
	assign out_a = in_a & in_b;
endmodule





