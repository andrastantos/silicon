////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic [7:0] sout1_b,
	output logic [7:0] sout1_g,
	output logic [7:0] sout1_r,

	output logic [7:0] uout1_b,
	output logic [7:0] uout1_g,
	output logic [7:0] uout1_r,

	output logic [7:0] uout2_b,
	output logic [7:0] uout2_g,
	output logic [7:0] uout2_r,

	output logic [7:0] uout3_b,
	output logic [7:0] uout3_g,
	output logic [7:0] uout3_r,

	output logic [7:0] uout4_b,
	output logic [7:0] uout4_g,
	output logic [7:0] uout4_r,

	input logic [7:0] uin1_b,
	input logic [7:0] uin1_g,
	input logic [7:0] uin1_r,

	input logic [7:0] uin2_b,
	input logic [7:0] uin2_g,
	input logic [7:0] uin2_r,

	input logic clk1,
	input logic clk2
);

	logic clk;
	logic [7:0] registered_b;
	logic [7:0] registered_g;
	logic [7:0] registered_r;
	logic reset;
	logic [7:0] reset_reg_b;
	logic [7:0] reset_reg_g;
	logic [7:0] reset_reg_r;
	logic [7:0] reset_reg2_b;
	logic [7:0] reset_reg2_g;
	logic [7:0] reset_reg2_r;

	always_ff @(posedge clk1) sout1_b <= uin1_b;
	always_ff @(posedge clk1) sout1_g <= uin1_g;
	always_ff @(posedge clk1) sout1_r <= uin1_r;
	always_ff @(posedge clk1) registered_b <= uin2_b;
	always_ff @(posedge clk1) registered_g <= uin2_g;
	always_ff @(posedge clk1) registered_r <= uin2_r;
	always_ff @(posedge clk2) uout2_b <= reset ? 8'h0 : uin2_b;
	always_ff @(posedge clk2) uout2_g <= reset ? 8'h0 : uin2_g;
	always_ff @(posedge clk2) uout2_r <= reset ? 8'h0 : uin2_r;
	always_ff @(posedge clk1) uout3_b <= reset ? 8'h0 : uin1_b;
	always_ff @(posedge clk1) uout3_g <= reset ? 8'h0 : uin1_g;
	always_ff @(posedge clk1) uout3_r <= reset ? 8'h0 : uin1_r;
	assign reset = uin2_r[0];
	always_ff @(posedge clk1) reset_reg_b <= uin2_r[4] ? uin2_b : uin1_b;
	always_ff @(posedge clk1) reset_reg_g <= uin2_r[4] ? uin2_g : uin1_g;
	always_ff @(posedge clk1) reset_reg_r <= uin2_r[4] ? uin2_r : uin1_r;
	always_ff @(posedge clk1) reset_reg2_b <= reset ? uin2_b : uin1_b;
	always_ff @(posedge clk1) reset_reg2_g <= reset ? uin2_g : uin1_g;
	always_ff @(posedge clk1) reset_reg2_r <= reset ? uin2_r : uin1_r;

	assign uout4_b = 8'hx;
	assign uout4_g = 8'hx;
	assign uout4_r = 8'hx;
	assign clk = clk1;
	assign uout1_b = registered_b;
	assign uout1_g = registered_g;
	assign uout1_r = registered_r;
endmodule


