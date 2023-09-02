////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic clk,
	input logic rst,
	input logic [9:0] paddr,
	input logic psel,
	input logic penable,
	output logic [31:0] prdata,
	input logic [31:0] pwdata,
	input logic pwrite,
	output logic pready
);

	logic [31:0] reg0;
	logic [15:0] reg1b;
	logic [15:0] reg1a;
	logic [7:0] reg2b;
	logic [7:0] reg2a;

	always_ff @(posedge clk) prdata <= rst ? 32'h0 : (paddr[3:0] == 1'h0 ? reg0 : 32'b0) | (paddr[3:0] == 1'h1 ? ({reg1a, reg1b}) : 32'b0) | (paddr[3:0] == 4'ha ? ({reg2a, 8'h0, reg2b, 8'h0}) : 32'b0) ;
	always_ff @(posedge clk) reg0 <= rst ? 32'h0 : paddr[9:4] == 7'h40 & psel & penable & pwrite & pready & paddr[3:0] == 1'h0 ? pwdata[31:0] : reg0;
	always_ff @(posedge clk) reg1b <= rst ? 16'h0 : paddr[9:4] == 7'h40 & psel & penable & pwrite & pready & paddr[3:0] == 1'h1 ? pwdata[15:0] : reg1b;
	always_ff @(posedge clk) reg1a <= rst ? 16'h0 : paddr[9:4] == 7'h40 & psel & penable & pwrite & pready & paddr[3:0] == 1'h1 ? pwdata[31:16] : reg1a;
	always_ff @(posedge clk) reg2b <= rst ? 8'h0 : paddr[9:4] == 7'h40 & psel & penable & pwrite & pready & paddr[3:0] == 4'ha ? pwdata[15:8] : reg2b;
	always_ff @(posedge clk) reg2a <= rst ? 8'h0 : paddr[9:4] == 7'h40 & psel & penable & pwrite & pready & paddr[3:0] == 4'ha ? pwdata[31:24] : reg2a;
	assign pready = 1'h1;

endmodule


