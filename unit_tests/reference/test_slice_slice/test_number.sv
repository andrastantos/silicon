////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic uout1,
	output logic [4:0] uout2,
	output logic [4:0] uout3,
	output logic [4:0] uout4,
	input logic [9:0] uin1,
	input logic uin2
);

	assign uout1 = uin1[3];
	assign uout2 = uin1[9:5];
	assign uout3 = {2'(uin2), uin1[0], 2'(uin1[2])};

	assign uout4 = 5'x;
endmodule


