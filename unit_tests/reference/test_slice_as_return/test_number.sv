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

	logic signed [5:0] u4_output_port;
	logic signed [5:0] u9_output_port;
	logic [7:0] daa_res;
	logic [3:0] daa_digit_2;
	logic [3:0] daa_digit_1;
	logic daa_step_1_carry;
	logic daa_step_2_carry;

	assign daa_digit_2 = u9_output_port[3:0];
	assign daa_digit_1 = u4_output_port[3:0];
	assign daa_step_1_carry = u4_output_port[4];
	assign daa_step_2_carry = u9_output_port[4];
	assign out_a = in_b + daa_step_1_carry + daa_step_2_carry;
	assign daa_res = {daa_digit_2, daa_digit_1};

	assign u4_output_port = in_c ? in_a - 1'h1 : in_a + 1'h1;
	assign u9_output_port = in_c ? in_a - 1'h1 : in_a + 1'h1;
	assign out_b = daa_res;
endmodule


