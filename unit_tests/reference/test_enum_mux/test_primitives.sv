////////////////////////////////////////////////////////////////////////////////
// Type definitions
////////////////////////////////////////////////////////////////////////////////
`define branch_ops__unknown 4'h0
`define branch_ops__cb_eq 4'h1
`define branch_ops__cb_ne 4'h2
`define branch_ops__cb_unk 4'he





////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic [3:0] in1,
	input logic [3:0] in2,
	input logic sel1,
	input logic sel2,
	input logic sel3,
	input logic sel_none,
	output logic [3:0] out1
);

	assign out1 = 
		(sel_none ? $signed(1'bX) : 4'b0) | 
		(sel1 ? in1 : 4'b0) | 
		(sel2 ? in2 : 4'b0) | 
		(sel3 ? `branch_ops__cb_eq : 4'b0) | 
		(sel_none | sel1 | sel2 | sel3 ? 4'b0 : `branch_ops__cb_unk);

endmodule


