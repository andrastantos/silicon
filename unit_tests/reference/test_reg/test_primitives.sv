////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic signed [4:0] sout1,
	output logic signed [4:0] uout1,
	output logic signed [4:0] uout2,
	output logic signed [4:0] uout3,
	output logic signed [4:0] uout4,
	input logic [1:0] uin1,
	input logic [3:0] uin2,
	input logic clk1,
	input logic clk2
);

	logic clk;
	logic [1:0] u_output_port;
	logic [3:0] registered;
	logic [3:0] u5_output_port;
	logic [1:0] u6_output_port;
	logic reset;
	logic [1:0] reset_reg;
	logic [1:0] reset_reg2;

	always_ff @(posedge clk1) u_output_port <= uin1;
	always_ff @(posedge clk1) registered <= uin2;
	always_ff @(posedge clk2) u5_output_port <= reset ? 4'0 : uin2;
	always_ff @(posedge clk1) u6_output_port <= reset ? 2'0 : uin1;
	assign reset = uin2[0];
	always_ff @(posedge clk1) reset_reg <= uin2[1] ? 2'h3 : uin1;
	always_ff @(posedge clk1) reset_reg2 <= reset ? 2'h2 : uin1;
	assign sout1 = u_output_port;
	assign uout1 = registered;
	assign uout2 = u5_output_port;
	assign uout3 = u6_output_port;

	assign uout4 = 5'x;
	assign clk = clk1;
endmodule


