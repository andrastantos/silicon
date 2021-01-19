////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic signed [10:0] sout1,
	output logic signed [10:0] sout2,
	output logic signed [10:0] sout3,
	output logic signed [10:0] sout4,
	output logic signed [10:0] sout5,
	input logic [1:0] val_in1,
	input logic [3:0] val_in2,
	input logic signed [3:0] val_in3,
	input logic signed [3:0] val_in4,
	input logic [7:0] default,
	input logic [1:0] sel_in1,
	input logic sel_in2,
	input logic signed [1:0] sel_in3,
	input logic signed sel_in4
);

	assign sout1 = sel_in1 ? val_in1 : 9'b0 | sel_in2 ? val_in2 : 9'b0 | sel_in3 ? val_in3 : 9'b0 | sel_in4 ? val_in4 : 9'b0 | default;
	assign sout2 = sel_in1 ? val_in1 : sel_in2 ? val_in2 : sel_in3 ? val_in3 : sel_in4 ? val_in4 : default;
	assign sout3 = sel_in1 ? val_in1 : sel_in2 ? val_in2 : sel_in3 ? val_in3 : sel_in4 ? val_in4 : default;
	assign sout4 = sel_in1 ? val_in1 : sel_in2 ? val_in2 : sel_in3 ? val_in3 : sel_in4 ? val_in4 : default;
	assign sout5 = sel_in1 ? val_in1 : sel_in2 ? val_in2 : sel_in3 ? val_in3 : sel_in4 ? val_in4 : default;

endmodule


