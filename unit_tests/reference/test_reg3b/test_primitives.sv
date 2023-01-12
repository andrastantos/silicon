////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic signed [4:0] uout3,
	input logic [1:0] uin1,
	input logic clk
);

	logic [1:0] u_output_port;
	logic u1_output_port;

	always_ff @(posedge clk) u_output_port <= u1_output_port ? 2'h0 : uin1;
	assign uout3 = u_output_port;

	assign u1_output_port = uin1[0];
endmodule


