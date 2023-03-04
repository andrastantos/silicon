////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic [3:0] uout1,
	output logic [3:0] uout2,
	output logic [3:0] uout3,
	output logic [3:0] uout4,
	output logic [3:0] uout5,
	output logic [3:0] uout6,
	output logic [3:0] uout7,
	output logic [3:0] uout8,
	output logic [3:0] uout9,
	output logic [3:0] uout10,
	output logic [3:0] uout11,
	output logic [3:0] uout12,
	output logic signed [3:0] sout1,
	output logic signed [3:0] sout4,
	output logic signed [3:0] sout5,
	input logic [3:0] uin1,
	input logic [3:0] uin2,
	input logic uin3,
	input logic [2:0] uin4,
	input logic [3:0] uin5,
	input logic signed [3:0] sin1,
	input logic signed [3:0] sin2,
	input logic signed [1:0] sin3,
	output logic signed [4:0] sout2,
	output logic signed [4:0] sout3,
	output logic lt_out,
	output logic le_out,
	output logic eq_out,
	output logic ne_out,
	output logic gt_out,
	output logic ge_out,
	output logic signed [95:0] slsh_out,
	output logic [95:0] ulsh_out,
	output logic signed [95:0] srsh_out,
	output logic [95:0] ursh_out
);

	logic [3:0] u24_output_port;
	logic [3:0] u27_output_port;
	logic [3:0] u35_output_port;
	logic [3:0] u38_output_port;
	logic [3:0] u46_output_port;
	logic [3:0] u49_output_port;
	logic [3:0] u57_output_port;
	logic [3:0] u60_output_port;

	assign uout1 = uin1 & uin2;
	assign sout1 = sin1 & sin1;
	assign uout2 = uin1 & uin2 & uin3;
	assign uout3 = uin1 & uin2 | uin1 & uin3;
	assign uout4 = uin1 | uin2 & uin3 | uin4;
	assign sout4 = sin1 & sin3 | sin1;
	assign sout5 = (sin1 | sin3) & sin1;
	assign uout7 = uin1 & (uin2 | uin3);
	assign uout8 = uin1 | uin2 & uin3;
	assign lt_out = sin1 < sin2;
	assign le_out = sin1 <= sin2;
	assign eq_out = sin1 == sin2;
	assign ne_out = sin1 != sin2;
	assign gt_out = sin1 > sin2;
	assign ge_out = sin1 >= sin2;
	assign uout9 = {uin1[3] & (uin2[0] | uin5[3]), uin1[2] & (uin2[1] | uin5[2]), uin1[1] & (uin2[2] | uin5[1]), uin1[0] & (uin2[3] | uin5[0])};
	assign uout10 = {u57_output_port[3], u46_output_port[2], u35_output_port[1], u24_output_port[0]};
	assign uout11 = {u27_output_port[0], u38_output_port[1], u49_output_port[2], u60_output_port[3]};
	assign sout2 = sin1 + sin2 + 5'b0;
	assign sout3 = sin1 - sin2 + 5'b0;
	assign slsh_out = (sin1 <<< uin1) + 19'b0;
	assign ulsh_out = (uin1 << uin1) + 19'b0;
	assign srsh_out = $signed(sin1 >>> uin1);
	assign ursh_out = uin1 >> uin1;

	assign uout5 = 4'hx;
	assign uout6 = 4'hx;
	assign uout12 = 4'hx;
	assign u24_output_port = uin1 & (uin2 | uin5);
	assign u27_output_port = uin1 & (uin2 | uin5);
	assign u35_output_port = uin1 & (uin2 | uin5);
	assign u38_output_port = uin1 & (uin2 | uin5);
	assign u46_output_port = uin1 & (uin2 | uin5);
	assign u49_output_port = uin1 & (uin2 | uin5);
	assign u57_output_port = uin1 & (uin2 | uin5);
	assign u60_output_port = uin1 & (uin2 | uin5);
endmodule


