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

	logic [15:0] x0_data;
	logic [15:0] x1_data;
	logic [15:0] x2_data;
	logic [15:0] x3_data;
	logic signed [12:0] x0_data2;
	logic signed [12:0] x1_data2;
	logic signed [12:0] x2_data2;
	logic signed [12:0] x3_data2;
	logic x0_valid;
	logic x1_valid;
	logic x2_valid;
	logic x3_valid;
	logic x0_ready;
	logic x1_ready;
	logic x2_ready;
	logic x3_ready;

	assign x3_data = in2_data;
	assign x3_data2 = in2_data2;
	assign x3_valid = in2_valid;
	assign x3_ready = out2_ready;

	assign out2_data = x3_data;
	assign x0_data = x3_data;
	assign x1_data = x3_data;
	assign x2_data = x3_data;
	assign out2_data2 = x3_data2;
	assign x0_data2 = x3_data2;
	assign x1_data2 = x3_data2;
	assign x2_data2 = x3_data2;
	assign out2_valid = x3_valid;
	assign x0_valid = x3_valid;
	assign x1_valid = x3_valid;
	assign x2_valid = x3_valid;
	assign in2_ready = x3_ready;
	assign x0_ready = x3_ready;
	assign x1_ready = x3_ready;
	assign x2_ready = x3_ready;
endmodule


