////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic signed [4:0] uout3,
	input logic [1:0] uin1,
	input logic clk
);

	logic [1:0] u_output_port;
	logic reset;

	always_ff @(posedge clk) u_output_port <= reset ? 2'h0 : uin1;
	assign reset = uin1[0];
	assign uout3 = u_output_port;

endmodule


