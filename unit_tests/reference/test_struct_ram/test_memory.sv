////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic [7:0] data_in_b,
	input logic [7:0] data_in_g,
	input logic [7:0] data_in_r,

	output logic [7:0] data_out_b,
	output logic [7:0] data_out_g,
	output logic [7:0] data_out_r,

	input logic [7:0] addr,
	input logic write_en,
	input logic clk
);

	Memory mem (
		.addr(addr),
		.clk(clk),
		.data_in_b(data_in_b),
		.data_in_g(data_in_g),
		.data_in_r(data_in_r),

		.data_out_b(data_out_b),
		.data_out_g(data_out_g),
		.data_out_r(data_out_r),

		.write_en(write_en)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// Memory
////////////////////////////////////////////////////////////////////////////////
module Memory (
	input logic [7:0] addr,
	input logic clk,
	input logic [7:0] data_in_b,
	input logic [7:0] data_in_g,
	input logic [7:0] data_in_r,

	output logic [7:0] data_out_b,
	output logic [7:0] data_out_g,
	output logic [7:0] data_out_r,

	input logic write_en
);

	logic [23:0] real_mem_data_out;

	logic [23:0] mem [255:0];
	logic [7:0] addr_reg;
	always @(posedge clk) begin
		if (write_en) begin
			mem[addr] <= {data_in_b, data_in_g, data_in_r};
		end
		addr_reg <= addr;
	end
	assign real_mem_data_out = mem[addr_reg];
	assign {data_out_b, data_out_g, data_out_r} = real_mem_data_out;

endmodule


