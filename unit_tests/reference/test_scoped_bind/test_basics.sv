////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic [7:0] out_a,
	output logic [7:0] out_b,
	output logic [7:0] out_c,
	output logic [7:0] out_d,
	output logic [7:0] out_e,
	output logic [7:0] out_f,
	output logic [7:0] out_g,
	output logic [7:0] out_h,
	output logic [7:0] out_i,
	input logic [7:0] in_a,
	input logic [7:0] in_b,
	input logic [7:0] in_c,
	input logic [7:0] in_d
);

	logic [7:0] a;

	assign a = in_a;
	assign out_e = in_b;
	assign out_c = in_c;
	assign out_g = in_d;

	assign out_i = 8'hx;
	assign out_f = in_c;
	assign out_h = in_d;
	assign out_a = a;
	assign out_b = a;
	assign out_d = a;
endmodule


