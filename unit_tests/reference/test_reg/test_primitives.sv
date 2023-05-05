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

	logic [1:0] u_output_port;
	logic [3:0] registered;
	logic [1:0] reset_reg;
	logic [1:0] reset_reg2;
	logic [3:0] u8_output_port;
	logic [1:0] u9_output_port;
	logic u8_reset_port;
	logic signed [4:0] registered_1;

	always_ff @(posedge clk1) u_output_port <= uin1;
	always_ff @(posedge clk1) registered <= uin2;
	always_ff @(posedge clk2) u8_output_port <= u8_reset_port ? 4'h0 : uin2;
	always_ff @(posedge clk1) u9_output_port <= u8_reset_port ? 2'h0 : uin1;
	always_ff @(posedge clk1) reset_reg <= uin2[1] ? 2'h3 : uin1;
	initial reset_reg <= 2'h3;
	always_ff @(posedge clk1) reset_reg2 <= u8_reset_port ? 2'h2 : uin1;
	initial reset_reg2 <= 2'h2;
	assign sout1 = u_output_port;
	assign registered_1 = registered;
	assign uout2 = u8_output_port;
	assign uout3 = u9_output_port;

	assign uout4 = 5'hx;
	assign u8_reset_port = uin2[0];
	assign uout1 = registered_1;
endmodule


