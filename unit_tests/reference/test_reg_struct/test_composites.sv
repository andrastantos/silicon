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
	logic [7:0] wire;
	logic [7:0] registered_g;
	logic [7:0] wire_1;
	logic [7:0] registered_r;
	logic [7:0] wire_2;
	logic reset;
	logic [7:0] reset_reg_b;
	logic [7:0] wire_3;
	logic [7:0] reset_reg_g;
	logic [7:0] wire_4;
	logic [7:0] reset_reg_r;
	logic [7:0] wire_5;
	logic [7:0] reset_reg2_b;
	logic [7:0] wire_6;
	logic [7:0] reset_reg2_g;
	logic [7:0] wire_7;
	logic [7:0] reset_reg2_r;
	logic [7:0] wire_8;

	always_ff @(posedge clk1) sout1_b <= uin1_b;
	always_ff @(posedge clk1) sout1_g <= uin1_g;
	always_ff @(posedge clk1) sout1_r <= uin1_r;
	always_ff @(posedge clk1) wire <= uin2_b;
	always_ff @(posedge clk1) wire_1 <= uin2_g;
	always_ff @(posedge clk1) wire_2 <= uin2_r;
	always_ff @(posedge clk2) uout2_b <= reset ? 8'0 : uin2_b;
	always_ff @(posedge clk2) uout2_g <= reset ? 8'0 : uin2_g;
	always_ff @(posedge clk2) uout2_r <= reset ? 8'0 : uin2_r;
	always_ff @(posedge clk1) uout3_b <= reset ? 8'0 : uin1_b;
	always_ff @(posedge clk1) uout3_g <= reset ? 8'0 : uin1_g;
	always_ff @(posedge clk1) uout3_r <= reset ? 8'0 : uin1_r;
	assign reset = uin2_r[0];
	always_ff @(posedge clk1) wire_3 <= uin1_b;
	always_ff @(posedge clk1) wire_4 <= uin1_g;
	always_ff @(posedge clk1) wire_5 <= uin1_r;
	always_ff @(posedge clk1) wire_6 <= reset ? uin1_b : uin1_b;
	always_ff @(posedge clk1) wire_7 <= reset ? uin1_g : uin1_g;
	always_ff @(posedge clk1) wire_8 <= reset ? uin1_r : uin1_r;

	assign uout4_b = 8'x;
	assign uout4_g = 8'x;
	assign uout4_r = 8'x;
	assign clk = clk1;
	assign uout1_b = wire;
	assign registered_b = wire;
	assign uout1_g = wire_1;
	assign registered_g = wire_1;
	assign uout1_r = wire_2;
	assign registered_r = wire_2;
	assign reset_reg_b = wire_3;
	assign reset_reg_g = wire_4;
	assign reset_reg_r = wire_5;
	assign reset_reg2_b = wire_6;
	assign reset_reg2_g = wire_7;
	assign reset_reg2_r = wire_8;
endmodule


