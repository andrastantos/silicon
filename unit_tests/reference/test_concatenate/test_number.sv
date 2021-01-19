////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic [15:0] uout1,
	output logic signed [15:0] sout1,
	input logic [3:0] uin1,
	input logic [3:0] uin2,
	input logic signed [3:0] sin1,
	input logic signed [3:0] sin2
);

	assign uout1 = {uin1, uin2};
	assign sout1 = signed'({sin1, uin1});

endmodule


