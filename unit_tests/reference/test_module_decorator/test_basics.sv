////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	output logic signed [4:0] out_a,
	output logic signed [4:0] out_b,
	output logic signed [4:0] out_c,
	output logic signed [4:0] out_d,
	output logic signed [4:0] out_e,
	output logic signed [4:0] out_f,
	input logic signed in_a,
	input logic signed in_b
);

	logic u3_output_port;
	logic [1:0] u4_output_port;
	logic [1:0] u5_output_port;

	assign out_d = u3_output_port;
	assign out_e = u4_output_port;
	assign out_f = u5_output_port;

	DecoratorModule u (
		.output_port(out_a),
		.a(in_a),
		.b(in_b)
	);

	DecoratorModule_2 u1 (
		.output_port(out_b),
		.b(in_b),
		.a(in_a)
	);

	DecoratorModule u2 (
		.output_port(out_c),
		.a(in_a),
		.b(in_b)
	);

	DecoratorModule_3 u3 (
		.output_port(u3_output_port),
		.b(in_b)
	);

	DecoratorModule_4 u4 (
		.output_port(u4_output_port),
		.a(in_a)
	);

	DecoratorModule_5 u5 (
		.output_port(u5_output_port)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// DecoratorModule_5
////////////////////////////////////////////////////////////////////////////////
module DecoratorModule_5 (
	output logic [1:0] output_port
);

	assign output_port = 2'h3;

endmodule


////////////////////////////////////////////////////////////////////////////////
// DecoratorModule_4
////////////////////////////////////////////////////////////////////////////////
module DecoratorModule_4 (
	output logic [1:0] output_port,
	input logic signed a
);

	assign output_port = a + 2'h2;

endmodule


////////////////////////////////////////////////////////////////////////////////
// DecoratorModule_3
////////////////////////////////////////////////////////////////////////////////
module DecoratorModule_3 (
	output logic output_port,
	input logic signed b
);

	assign output_port = 1'h1 + b;

endmodule


////////////////////////////////////////////////////////////////////////////////
// DecoratorModule_2
////////////////////////////////////////////////////////////////////////////////
module DecoratorModule_2 (
	output logic signed [1:0] output_port,
	input logic signed b,
	input logic signed a
);

	assign output_port = a + b;

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


