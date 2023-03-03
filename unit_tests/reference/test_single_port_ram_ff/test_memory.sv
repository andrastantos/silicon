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


////////////////////////////////////////////////////////////////////////////////
// Memory
////////////////////////////////////////////////////////////////////////////////
module Memory (
	input logic [7:0] addr,
	input logic clk,
	input logic [7:0] data_in,
	output logic [7:0] data_out,
	input logic write_en
);

	logic [7:0] mem [255:0];
	always @(posedge clk) begin
		if (write_en) begin
			mem[addr] <= data_in;
		end
	end
	assign data_out = mem[addr];

endmodule


