////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic [15:0] uout1,
	output logic signed [15:0] sout1,
	output logic [15:0] uout2,
	output logic signed [15:0] sout2,
	input logic in1,
	input logic in2,
	output logic out1
);

	assign uout1 = 6'h2a;
	assign sout1 = 6'h2b;
	assign sout2 = -7'sh2d;

	assign uout2 = 16'hx;
	assign out1 = in1;
endmodule


