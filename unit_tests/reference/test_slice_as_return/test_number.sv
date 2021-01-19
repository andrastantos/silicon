////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	output logic [4:0] out_a,
	output logic [7:0] out_b,
	input logic [3:0] in_a,
	input logic [3:0] in_b,
	input logic in_c
);

	logic [3:0] daa_digit_2;
	logic [3:0] daa_digit_1;
	logic daa_step_1_carry;
	logic daa_step_2_carry;
	logic [7:0] daa_res;

	assign daa_digit_2 = (in_c ? in_a - 1'h1 : in_a + 1'h1)[3:0];
	assign daa_digit_1 = (in_c ? in_a - 1'h1 : in_a + 1'h1)[3:0];
	assign daa_step_1_carry = (in_c ? in_a - 1'h1 : in_a + 1'h1)[4];
	assign daa_step_2_carry = (in_c ? in_a - 1'h1 : in_a + 1'h1)[4];
	assign out_a = in_b + daa_step_1_carry + daa_step_2_carry;
	assign daa_res = {daa_digit_2, daa_digit_1};

	assign out_b = daa_res;
endmodule


