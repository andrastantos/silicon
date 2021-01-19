////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	output logic signed [4:0] out_a,
	output logic signed [4:0] out_b,
	output logic signed [4:0] out_c,
	input logic signed in_a,
	input logic signed in_b
);

	logic u2_output_port;

	assign out_c = u2_output_port;

	DecoratorModule u (
		.output_port(out_a),
		.a(in_a),
		.b(in_b)
	);

	DecoratorModule u1 (
		.output_port(out_b),
		.a(in_a),
		.b(in_b)
	);

	DecoratorModule_2 u2 (
		.output_port(u2_output_port),
		.a(in_a)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// DecoratorModule_2
////////////////////////////////////////////////////////////////////////////////
module DecoratorModule_2 (
	output logic output_port,
	input logic signed a
);

	assign output_port = a + 1'h1;

endmodule


////////////////////////////////////////////////////////////////////////////////
// DecoratorModule
////////////////////////////////////////////////////////////////////////////////
module DecoratorModule (
	output logic signed [1:0] output_port,
	input logic signed a,
	input logic signed b
);

	assign output_port = a + b;

endmodule


