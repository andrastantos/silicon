////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic [7:0] out_a,
	input logic [7:0] in_a
);

	logic but;
	logic bit_1;

	assign bit_1 = in_a[7];
	assign out_a = {bit_1, in_a[6], in_a[5], in_a[4], in_a[3], in_a[2], in_a[1], in_a[0]};

	assign but = bit_1;
endmodule


