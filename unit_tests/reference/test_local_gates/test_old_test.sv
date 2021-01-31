////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic in_1,
	input logic in_2,
	input logic in_3,
	input logic in_4,
	output logic out_1,
	output logic out_2,
	output logic out_3,
	output logic out_4,
	output logic out_5,
	output logic out_6
);

	logic xxx;
	logic xxxx;
	logic ttt;
	logic tttt;
	logic A_out_a;
	logic c;
	logic u1_out_a;
	logic out_a;
	logic yyyy;
	logic outc;
	logic d;
	logic dd;

	assign out_5 = 1'h0;
	assign out_6 = 1'h1;

	and_gate B (
		.in_a(1'x),
		.in_b(1'x),
		.out_a(tttt)
	);

	and_gate A (
		.in_a(tttt),
		.in_b(tttt),
		.out_a(A_out_a)
	);

	and_gate u (
		.in_a(A_out_a),
		.in_b(tttt),
		.out_a(c)
	);

	generic_and_gate u1 (
		.in_a(A_out_a),
		.in_b(tttt),
		.out_a(u1_out_a)
	);

	full_adder FA (
		.in_a(in_1),
		.in_b(in_2),
		.in_c(in_3),
		.out_a(yyyy),
		.out_c(outc)
	);

	and_gate D (
		.in_a(c),
		.in_b(u1_out_a),
		.out_a(dd)
	);

	assign out_2 = in_4;
	assign xxx = in_4;
	assign xxxx = in_4;
	assign out_4 = 1'x;
	assign ttt = tttt;
	assign out_1 = yyyy;
	assign out_a = yyyy;
	assign out_3 = outc;
	assign d = dd;
endmodule


////////////////////////////////////////////////////////////////////////////////
// full_adder
////////////////////////////////////////////////////////////////////////////////
module full_adder (
	input logic in_a,
	input logic in_b,
	input logic in_c,
	output logic out_a,
	output logic out_c
);

	logic u_out_a;
	logic u2_out_a;
	logic u3_out_a;
	logic u4_out_a;
	logic u5_out_a;

	xor_gate2 u (
		.in_a(in_b),
		.in_b(in_c),
		.out_a(u_out_a)
	);

	xor_gate1 u1 (
		.in_a(in_a),
		.in_b(u_out_a),
		.out_a(out_a)
	);

	and_gate2 u2 (
		.in_a(in_a),
		.in_b(in_c),
		.out_a(u2_out_a)
	);

	and_gate3 u3 (
		.in_a(in_b),
		.in_b(in_c),
		.out_a(u3_out_a)
	);

	and_gate1 u4 (
		.in_a(in_a),
		.in_b(in_b),
		.out_a(u4_out_a)
	);

	or_gate u5 (
		.in_a(u2_out_a),
		.in_b(u3_out_a),
		.out_a(u5_out_a)
	);

	or_gate u6 (
		.in_a(u4_out_a),
		.in_b(u5_out_a),
		.out_a(out_c)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// or_gate
////////////////////////////////////////////////////////////////////////////////
module or_gate (
	input logic in_a,
	input logic in_b,
	output logic out_a
);
	assign out_a = in_a | in_b;
endmodule





////////////////////////////////////////////////////////////////////////////////
// and_gate1
////////////////////////////////////////////////////////////////////////////////
module and_gate1 (
	input logic in_a,
	input logic in_b,
	output logic out_a
);
	assign out_a = in_a & in_b;
endmodule





////////////////////////////////////////////////////////////////////////////////
// and_gate3
////////////////////////////////////////////////////////////////////////////////
module and_gate3 (
	input logic in_a,
	input logic in_b,
	output logic out_a
);
	assign out_a = in_a & in_b;
endmodule





////////////////////////////////////////////////////////////////////////////////
// and_gate2
////////////////////////////////////////////////////////////////////////////////
module and_gate2 (
	input logic in_a,
	input logic in_b,
	output logic out_a
);
	assign out_a = in_a & in_b;
endmodule





////////////////////////////////////////////////////////////////////////////////
// xor_gate1
////////////////////////////////////////////////////////////////////////////////
module xor_gate1 (
	input logic in_a,
	input logic in_b,
	output logic out_a
);
	assign out_a = in_a ^ in_b;
endmodule





////////////////////////////////////////////////////////////////////////////////
// xor_gate2
////////////////////////////////////////////////////////////////////////////////
module xor_gate2 (
	input logic in_a,
	input logic in_b,
	output logic out_a
);
	assign out_a = in_a ^ in_b;
endmodule





////////////////////////////////////////////////////////////////////////////////
// generic_and_gate
////////////////////////////////////////////////////////////////////////////////
module generic_and_gate (
	input logic in_a,
	input logic in_b,
	output logic out_a
);
	//a = 3, b = 42
	assign out_a = in_a & in_b;
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





