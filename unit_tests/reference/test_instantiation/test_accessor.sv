////////////////////////////////////////////////////////////////////////////////
// Test
////////////////////////////////////////////////////////////////////////////////
module Test (
	input logic [7:0] in_a,
	output logic [7:0] out_1,
	output logic [7:0] out_2,
	output logic [7:0] out_3
);

	logic u_output;
	logic u1_output;

	Parity u (
		.input(in_a),
		.output(u_output)
	);

	Parity_2 u1 (
		.input(in_a),
		.output(u1_output)
	);

	// Assignments for outputs
	assign out_1 = u_output;
	assign out_2 = u1_output;
	assign out_3 = 8'bX;
endmodule


////////////////////////////////////////////////////////////////////////////////
// Parity
////////////////////////////////////////////////////////////////////////////////
module Parity (
	input logic [7:0] input,
	output logic output
);

	// Assignments for outputs
	assign output = input[0] ^ input[1] ^ input[2] ^ input[3] ^ input[4] ^ input[5] ^ input[6] ^ input[7];
endmodule


////////////////////////////////////////////////////////////////////////////////
// Parity_2
////////////////////////////////////////////////////////////////////////////////
module Parity_2 (
	input logic [7:0] input,
	output logic output
);

	// Assignments for outputs
	assign output = input[0] ^ input[1] ^ input[2] ^ input[3] ^ input[4] ^ input[5] ^ input[6] ^ input[7];
endmodule


