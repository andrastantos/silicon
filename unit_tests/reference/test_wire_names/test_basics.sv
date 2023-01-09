////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic out_a,
	output logic out_b,
	output logic out_aa,
	output logic out_bb,
	input logic in_a,
	input logic in_b
);

	logic aa;
	logic a;
	logic bb;
	logic b;

	assign a = in_a;
	assign b = in_b;

	assign out_a = a;
	assign out_aa = a;
	assign aa = a;
	assign out_b = b;
	assign out_bb = b;
	assign bb = b;
endmodule


