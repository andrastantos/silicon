////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic [13:0] data_in_a,
	output logic [13:0] data_out_a,
	input logic [13:0] data_in_b,
	output logic [13:0] data_out_b,
	input logic [5:0] addr_a,
	input logic [5:0] addr_b,
	input logic write_en_a,
	input logic write_en_b,
	input logic clk
);

	Memory mem (
		.port1_addr(addr_a),
		.port1_clk(clk),
		.port2_addr(addr_b),
		.port2_clk(clk),
		.port1_data_out(data_out_a),
		.port1_data_in(data_in_a),
		.port1_write_en(write_en_a),
		.port2_data_out(data_out_b),
		.port2_data_in(data_in_b),
		.port2_write_en(write_en_b)
	);

endmodule


