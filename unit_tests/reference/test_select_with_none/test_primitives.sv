////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic signed [4:0] sout1,
	input logic [1:0] uin1,
	input logic [3:0] uin2,
	input logic signed [3:0] sin1,
	input logic signed [3:0] sin2,
	input logic [1:0] sel_in
);

	assign sout1 = sel_in == 0 ? uin1 : 5'b0 | sel_in == 1 ? uin2 : 5'b0 | sel_in == 2 ? sin1 : 5'b0 | sel_in == 3 ? sin2 : 5'b0 | sel_in == 4 ? 5'hx : 5'b0;

endmodule


