////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic [7:0] in_1_r,
	input logic [7:0] in_1_g,
	input logic [7:0] in_1_b,

	output logic [7:0] out_1_r,
	output logic [7:0] out_1_g,
	output logic [7:0] out_1_b
);

	logic [7:0] in_1_r_1;
	logic [7:0] in_1_1_r;
	logic [7:0] in_1_1_g;
	logic [7:0] in_1_1_b;

	assign in_1_1_r = in_1_r;
	assign in_1_1_g = in_1_g;
	assign in_1_1_b = in_1_b;

	assign in_1_r_1 = in_1_r;
	assign out_1_r = in_1_1_r;
	assign out_1_g = in_1_1_g;
	assign out_1_b = in_1_1_b;
endmodule


