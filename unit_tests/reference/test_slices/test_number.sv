////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic uout1,
	output logic [1:0] uout2,
	output logic signed [7:0] sout1,
	output logic signed [7:0] sout4,
	input logic uin1,
	input logic [1:0] uin2,
	input logic [2:0] uin3,
	input logic [3:0] uin4,
	input logic [4:0] uin5,
	input logic signed sin1,
	input logic signed [1:0] sin2,
	input logic signed [2:0] sin3,
	input logic signed [3:0] sin4,
	input logic signed [4:0] sin5
);

	assign uout1 = uin1;
	assign uout2 = {uin1, uin1};
	assign sout1 = sin1[0];

	assign sout4 = 8'x;
endmodule


