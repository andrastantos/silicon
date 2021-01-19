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

	assign out_a = in_a;
	assign out_aa = in_a;
	assign aa = in_a;
	assign a = in_a;
	assign out_b = in_b;
	assign out_bb = in_b;
	assign bb = in_b;
	assign b = in_b;
endmodule


