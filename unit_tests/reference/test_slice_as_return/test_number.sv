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

	assign daa_res = {u9_output_port[3:0], u4_output_port[3:0]};
	assign out_a = in_b + u4_output_port[4] + 5'b0 + u9_output_port[4];

	assign u4_output_port = in_c ? in_a - 1'h1 + 5'b0 : in_a + 1'h1 + 5'b0;
	assign u9_output_port = in_c ? in_a - 1'h1 + 5'b0 : in_a + 1'h1 + 5'b0;
	assign out_b = daa_res;
endmodule


