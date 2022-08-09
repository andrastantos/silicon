////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic clk,
	input logic rst,
	input logic [31:0] fetch,
	output logic [31:0] push_data
);

	logic [31:0] sfd;
	logic [15:0] u1_output_port;
	logic [15:0] u3_output_port;
	logic [15:0] u5_output_port;
	logic [15:0] u7_output_port;
	logic s1;
	logic [31:0] inst_btm_top;
	logic [31:0] btm_inst_reg;

	always_ff @(posedge clk) u1_output_port <= rst ? 16'h0 : fetch[31:16];
	always_ff @(posedge clk) u3_output_port <= rst ? 16'h0 : fetch[15:0];
	always_ff @(posedge clk) u5_output_port <= rst ? 16'h0 : fetch[31:16];
	always_ff @(posedge clk) u7_output_port <= rst ? 16'h0 : fetch[15:0];
	assign s1 = 1'h1;
	assign inst_btm_top = s1 ? fetch : btm_inst_reg;
	assign push_data = {u5_output_port, u7_output_port};
	assign btm_inst_reg = {u1_output_port, u3_output_port};

	assign sfd = fetch;
endmodule


