////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic [7:0] in_a_data,
	output logic in_a_ready,
	input logic in_a_valid,

	output logic [7:0] out_a_data,
	input logic out_a_ready,
	output logic out_a_valid,

	input logic [7:0] x_in
);

	assign in_a_ready = out_a_ready & in_a_valid;

	assign out_a_valid = 1'hx;
	assign out_a_data = x_in;
endmodule


