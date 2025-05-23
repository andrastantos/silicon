////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	output logic [4:0] out_a,
	output logic [4:0] out_b,
	input logic [2:0] in_a,
	input logic [2:0] in_b
);

	logic u_output_port;
	logic [3:0] u1_output_port;

	assign out_a = u_output_port;
	assign out_b = u1_output_port;

	DecoratorModule u (
		.output_port(u_output_port),
		.a(in_a)
	);

	DecoratorModule_2 u1 (
		.output_port(u1_output_port),
		.a(in_a[2:0]),
		.b(in_b[1])
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// DecoratorModule_2
////////////////////////////////////////////////////////////////////////////////
module DecoratorModule_2 (
	output logic [3:0] output_port,
	input logic [2:0] a,
	input logic b
);

	assign output_port = a + b;

endmodule


////////////////////////////////////////////////////////////////////////////////
// DecoratorModule
////////////////////////////////////////////////////////////////////////////////
module DecoratorModule (
	output logic output_port,
	input logic [2:0] a
);

	assign output_port = a[0];

endmodule


