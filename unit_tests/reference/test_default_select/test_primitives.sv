////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic [2:0] i,
	input logic [1:0] s,
	input logic d,
	output logic o
);

	always @(*) begin
	    unique case (s)
	        2'd0: o = i[0];
	        2'd1: o = i[1];
	        2'd2: o = i[2];
	        default: o = d;
	    endcase
	end

endmodule


