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
		.port_a_addr(addr_a),
		.port_a_clk(clk),
		.port_b_addr(addr_b),
		.port_b_clk(clk),
		.port_a_data_out(data_out_a),
		.port_a_data_in(data_in_a),
		.port_a_write_en(write_en_a),
		.port_b_data_out(data_out_b),
		.port_b_data_in(data_in_b),
		.port_b_write_en(write_en_b)
	);

endmodule


