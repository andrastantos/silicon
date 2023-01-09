////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic [15:0] in2_data,
	input logic signed [12:0] in2_data2,
	output logic in2_ready,
	input logic in2_valid,

	output logic [15:0] out2_data,
	output logic signed [12:0] out2_data2,
	input logic out2_ready,
	output logic out2_valid
);

	logic [15:0] x1_data;
	logic signed [12:0] x1_data2;
	logic x1_valid;
	logic x1_ready;

	assign x1_data = in2_data;
	assign x1_data2 = in2_data2;
	assign x1_valid = in2_valid;
	assign x1_ready = out2_ready;

	assign out2_data = x1_data;
	assign out2_data2 = x1_data2;
	assign out2_valid = x1_valid;
	assign in2_ready = x1_ready;
endmodule


