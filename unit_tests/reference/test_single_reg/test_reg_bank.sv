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

	always_ff @(posedge clk) prdata <= rst ? 32'h0 : (1'h1 ? reg0 : 32'b0) ;
	always_ff @(posedge clk) reg0 <= rst ? 32'h0 : paddr[9:0] == 11'h400 & psel & penable & pwrite & pready & 1'h1 ? pwdata[31:0] : reg0;
	assign pready = 1'h1;

endmodule


