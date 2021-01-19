////////////////////////////////////////////////////////////////////////////////
// test_self_wire
////////////////////////////////////////////////////////////////////////////////
module test_self_wire (
	input logic n_cs,
	input logic [7:0] data_in,
	output logic [7:0] data_out,
	input logic n_wr,
	input logic clk,
	input logic rst
);

	logic wr_en;
	logic [7:0] ddd;
	logic [7:0] r0_horizontal_total;
	logic rd_en;

	assign wr_en =  ~ n_cs &  ~ n_wr;
	assign ddd = wr_en ? data_in : r0_horizontal_total;
	always_ff @(posedge clk) r0_horizontal_total <= rst ? 8'b0 : ddd;
	assign rd_en =  ~ n_cs & n_wr;
	assign data_out = rd_en ? 1'h0 : r0_horizontal_total;

endmodule


