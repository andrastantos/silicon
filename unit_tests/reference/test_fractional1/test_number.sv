////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic [7:0] in1,
	input logic [7:0] in2,
	output logic [9:0] outp
);

	assign outp = { in1, 1'b0 } + in2;

endmodule

