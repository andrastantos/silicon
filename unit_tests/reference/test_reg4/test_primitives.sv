////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic signed [4:0] sout1,
	input logic [1:0] uin1,
	input logic clk1
);

	logic [1:0] u2_output_port;

	always_ff @(posedge (clk1 & uin1[0])) u2_output_port <= uin1;
	assign sout1 = u2_output_port;

endmodule

