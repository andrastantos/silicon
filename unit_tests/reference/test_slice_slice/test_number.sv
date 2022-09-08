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

	logic [3:0] u1_output_port;
	logic [6:0] u4_output_port;
	logic [5:0] u3_output_port;

	assign uout1 = u1_output_port[1];
	assign uout2 = u3_output_port[5:1];
	assign uout3 = {2'(uin2), uin1[0], 2'(uin1[2])};

	assign uout4 = 5'hx;
	assign u1_output_port = uin1[5:2];
	assign u4_output_port = uin1[9:3];
	assign u3_output_port = u4_output_port[6:1];
endmodule


