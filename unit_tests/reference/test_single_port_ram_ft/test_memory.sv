////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic [7:0] data_in,
	output logic [7:0] data_out,
	input logic [7:0] addr,
	input logic write_en,
	input logic clk
);

	Memory mem (
		.addr(addr),
		.clk(clk),
		.data_in(data_in),
		.data_out(data_out),
		.write_en(write_en)
	);

endmodule


