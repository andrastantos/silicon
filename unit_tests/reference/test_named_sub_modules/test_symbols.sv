////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic in_1,
	input logic in_2,
	output logic out_1
);

	test_symbols_and_gate A (
		.in_a(in_1),
		.in_b(in_2),
		.out_a(out_1)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// test_symbols_and_gate
////////////////////////////////////////////////////////////////////////////////
module test_symbols_and_gate (
	input logic in_a,
	input logic in_b,
	output logic out_a
);

	assign out_a = in_a & in_b;

endmodule


