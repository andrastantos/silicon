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
		.port_b_data_in(data_in_b),
		.port_b_write_en(write_en_b)
	);

	assign data_out_b = 14'bX;
endmodule


////////////////////////////////////////////////////////////////////////////////
// Memory
////////////////////////////////////////////////////////////////////////////////
module Memory (
	input logic [5:0] port_a_addr,
	input logic port_a_clk,
	input logic [5:0] port_b_addr,
	input logic port_b_clk,
	output logic [13:0] port_a_data_out,
	input logic [13:0] port_b_data_in,
	input logic port_b_write_en
);

	reg [13:0] mem[0:63];

	initial begin
		$readmemb("config.bin", mem);
	end

	always @(posedge port_b_clk) begin
		if (port_b_write_en) begin
			mem[port_b_addr] <= port_b_data_in;
		end
	end

	wire [5:0] port_a_addr_reg;
	always @(posedge port_a_clk) begin
		port_a_addr_reg <= port_a_addr;
	end
	port_a_data_out <= mem[port_a_addr_reg];

endmodule


