////////////////////////////////////////////////////////////////////////////////
// Test
////////////////////////////////////////////////////////////////////////////////
module Test (
	input logic [7:0] in_a,
	output logic [7:0] out_1,
	output logic [7:0] out_2,
	output logic [7:0] out_3
);

	logic u_output_port;
	logic u1_output_port;

	assign out_1 = u_output_port;
	assign out_2 = u1_output_port;

	Parity u (
		.input_port(in_a),
		.output_port(u_output_port)
	);

	Parity u1 (
		.input_port(in_a),
		.output_port(u1_output_port)
	);

	assign out_3 = 8'hx;
endmodule


////////////////////////////////////////////////////////////////////////////////
// Parity
////////////////////////////////////////////////////////////////////////////////
module Parity (
	input logic [7:0] input_port,
	output logic output_port
);

	assign output_port = input_port[0];

endmodule


