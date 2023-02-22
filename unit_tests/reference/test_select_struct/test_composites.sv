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

	input logic [1:0] sel_in
);

	always @(*) begin
	    unique case (sel_in)
	        2'd0: out_port_b = in1_b;
	        2'd1: out_port_b = in2_b;
	        2'd2: out_port_b = in3_b;
	        2'd3: out_port_b = in4_b;
	    endcase
	end
	always @(*) begin
	    unique case (sel_in)
	        2'd0: out_port_g = in1_g;
	        2'd1: out_port_g = in2_g;
	        2'd2: out_port_g = in3_g;
	        2'd3: out_port_g = in4_g;
	    endcase
	end
	always @(*) begin
	    unique case (sel_in)
	        2'd0: out_port_r = in1_r;
	        2'd1: out_port_r = in2_r;
	        2'd2: out_port_r = in3_r;
	        2'd3: out_port_r = in4_r;
	    endcase
	end

endmodule


