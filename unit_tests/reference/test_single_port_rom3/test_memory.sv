////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	output logic [7:0] data_out,
	input logic [7:0] addr,
	input logic clk
);

	Memory mem (
		.addr(addr),
		.clk(clk),
		.data_out(data_out)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// Memory
////////////////////////////////////////////////////////////////////////////////
module Memory (
	input logic [7:0] addr,
	input logic clk,
	output logic [7:0] data_out
);

	wire [7:0] mem [255:0];
	initial begin
		mem[0] <= 8'h0;
		mem[1] <= 8'h1;
		mem[2] <= 8'h2;
		mem[3] <= 8'h3;
		mem[4] <= 8'h4;
		mem[5] <= 8'h5;
		mem[6] <= 8'h6;
		mem[7] <= 8'h7;
		mem[8] <= 8'h8;
		mem[9] <= 8'h9;
		mem[10] <= 8'ha;
		mem[11] <= 8'hb;
		mem[12] <= 8'hc;
		mem[13] <= 8'hd;
		mem[14] <= 8'he;
		mem[15] <= 8'hf;
		mem[16] <= 8'h10;
		mem[17] <= 8'h11;
		mem[18] <= 8'h12;
		mem[19] <= 8'h13;
	end
	wire [7:0] addr_reg;
	always @(posedge clk) begin
	    addr_reg <= addr;
	end
	data_out <= mem[addr_reg];

endmodule


