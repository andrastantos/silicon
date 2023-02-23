////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic [7:0] out_port_b,
	output logic [7:0] out_port_g,
	output logic [7:0] out_port_r,

	input logic [7:0] in1_b,
	input logic [7:0] in1_g,
	input logic [7:0] in1_r,

	input logic [7:0] in2_b,
	input logic [7:0] in2_g,
	input logic [7:0] in2_r,

	input logic [7:0] in3_b,
	input logic [7:0] in3_g,
	input logic [7:0] in3_r,

	input logic [7:0] in4_b,
	input logic [7:0] in4_g,
	input logic [7:0] in4_r,

	input logic [3:0] sel_in
);

	assign out_port_b = 
		(sel_in[0] ? in1_b : 8'b0) | 
		(sel_in[1] ? in2_b : 8'b0) | 
		(sel_in[2] ? in3_b : 8'b0) | 
		(sel_in[3] ? in4_b : 8'b0) ;
	assign out_port_g = 
		(sel_in[0] ? in1_g : 8'b0) | 
		(sel_in[1] ? in2_g : 8'b0) | 
		(sel_in[2] ? in3_g : 8'b0) | 
		(sel_in[3] ? in4_g : 8'b0) ;
	assign out_port_r = 
		(sel_in[0] ? in1_r : 8'b0) | 
		(sel_in[1] ? in2_r : 8'b0) | 
		(sel_in[2] ? in3_r : 8'b0) | 
		(sel_in[3] ? in4_r : 8'b0) ;

endmodule


