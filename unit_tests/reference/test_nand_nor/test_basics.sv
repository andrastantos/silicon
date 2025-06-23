////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic [1:0] in_a,
	input logic [1:0] in_b,
	input logic [3:0] in_c,
	output logic [3:0] out_nor,
	output logic [1:0] out_nand
);

	assign out_nor = ~(in_a | in_b | in_c);
	assign out_nand = ~(in_a & in_b);

endmodule


