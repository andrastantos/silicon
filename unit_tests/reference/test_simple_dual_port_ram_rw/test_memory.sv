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
		.port2_data_in(data_in_b),
		.port2_write_en(write_en_b)
	);

	assign data_out_b = 14'bX;
endmodule


////////////////////////////////////////////////////////////////////////////////
// Memory
////////////////////////////////////////////////////////////////////////////////
module Memory (
	input logic [5:0] port1_addr,
	input logic port1_clk,
	input logic [5:0] port2_addr,
	input logic port2_clk,
	output logic [13:0] port1_data_out,
	input logic [13:0] port2_data_in,
	input logic port2_write_en
);

	reg [13:0] mem[0:63];

	initial begin
		$readmemb("config.bin", mem);
	end

	wire [5:0] port1_addr_reg;
	always @(posedge port1_clk) begin
		port1_addr_reg <= port1_addr;
	end
	port1_data_out <= mem[port1_addr_reg];

	always @(posedge port1_clk) begin
		if (port2_write_en) begin
			mem[port2_addr] <= port2_data_in;
		end
	end


endmodule


