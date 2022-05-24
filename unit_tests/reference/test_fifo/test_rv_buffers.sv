////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic [7:0] in1_data,
	output logic in1_ready,
	input logic in1_valid,

	output logic [7:0] out1_data,
	input logic out1_ready,
	output logic out1_valid,

	input logic clk,
	input logic rst
);

	Fifo dut (
		.input_port_data(in1_data),
		.input_port_ready(in1_ready),
		.input_port_valid(in1_valid),

		.output_port_data(out1_data),
		.output_port_ready(out1_ready),
		.output_port_valid(out1_valid),

		.clock_port(clk),
		.reset_port(rst)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// Fifo
////////////////////////////////////////////////////////////////////////////////
module Fifo (
	input logic [7:0] input_port_data,
	output logic input_port_ready,
	input logic input_port_valid,

	output logic [7:0] output_port_data,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port
);

	logic [7:0] input_data_data;
	logic push_will_wrap;
	logic push;
	logic [3:0] u12_output_port;
	logic [3:0] next_push_addr;
	logic pop_will_wrap;
	logic pop;
	logic [3:0] u20_output_port;
	logic [3:0] next_pop_addr;
	logic next_looped;
	logic next_empty_or_full;
	logic next_empty;
	logic next_full;
	logic [3:0] push_addr;
	logic [3:0] pop_addr;
	logic empty;
	logic full;
	logic looped;
	logic [7:0] output_data_data;

	assign input_port_ready =  ~ full;
	assign output_port_valid =  ~ empty;
	assign push_will_wrap = push_addr == 4'h9;
	assign push =  ~ full & input_port_valid;
	assign next_push_addr = push ? u12_output_port : push_addr;
	assign pop_will_wrap = pop_addr == 4'h9;
	assign pop =  ~ empty & output_port_ready;
	assign next_pop_addr = pop ? u20_output_port : pop_addr;
	assign next_looped = push != 1'h1 & pop != 1'h1 ? looped : 1'b0 | push == 1'h1 & pop != 1'h1 ? push_will_wrap ? 1'h1 : looped : 1'b0 | push != 1'h1 & pop == 1'h1 ? pop_will_wrap ? 1'h0 : looped : 1'b0 | push == 1'h1 & pop == 1'h1 ? push_will_wrap != 1'h1 & pop_will_wrap != 1'h1 ? looped : 1'b0 | push_will_wrap == 1'h1 & pop_will_wrap != 1'h1 ? 1'h1 : 1'b0 | push_will_wrap != 1'h1 & pop_will_wrap == 1'h1 ? 1'h0 : 1'b0 | push_will_wrap == 1'h1 & pop_will_wrap == 1'h1 ? looped : 1'b0  : 1'b0 ;
	assign next_empty_or_full = next_push_addr == next_pop_addr;
	assign next_empty = next_empty_or_full ?  ~ next_looped : 1'h0;
	assign next_full = next_empty_or_full ? next_looped : 1'h0;
	always_ff @(posedge clock_port) push_addr <= reset_port ? 4'h0 : next_push_addr;
	always_ff @(posedge clock_port) pop_addr <= reset_port ? 4'h0 : next_pop_addr;
	always_ff @(posedge clock_port) empty <= reset_port ? 1'h0 : next_empty;
	always_ff @(posedge clock_port) full <= reset_port ? 1'h0 : next_full;
	always_ff @(posedge clock_port) looped <= reset_port ? 1'h0 : next_looped;

	ExplicitAdaptor u12 (
		.input_port(push_will_wrap ? 1'h0 : push_addr + 1'h1),
		.output_port(u12_output_port)
	);

	ExplicitAdaptor u20 (
		.input_port(pop_will_wrap ? 1'h0 : pop_addr + 1'h1),
		.output_port(u20_output_port)
	);

	Memory buffer_1 (
		.port1_addr(push_addr),
		.port1_clk(clock_port),
		.port2_addr(next_pop_addr),
		.port2_clk(clock_port),
		.port1_data_in_data(input_port_data),

		.port1_write_en(push),
		.port2_data_out_data(output_data_data)
	);

	assign input_data_data = input_port_data;
	assign output_port_data = output_data_data;
endmodule


////////////////////////////////////////////////////////////////////////////////
// Memory
////////////////////////////////////////////////////////////////////////////////
module Memory (
	input logic [3:0] port1_addr,
	input logic port1_clk,
	input logic [3:0] port2_addr,
	input logic port2_clk,
	input logic [7:0] port1_data_in_data,
	input logic port1_write_en,
	output logic [7:0] port2_data_out_data
);

	logic [7:0] real_mem_port2_data_out;

	reg [7:0] mem[0:15];

	always @(posedge port1_clk) begin
		if (port1_write_en) begin
			mem[port1_addr] <= {port1_data_in_data};
		end
	end

	logic [3:0] port2_addr_reg;
	always @(posedge port1_clk) begin
		port2_addr_reg <= port2_addr;
	end
	assign real_mem_port2_data_out = mem[port2_addr_reg];

	assign {port2_data_out_data} = real_mem_port2_data_out;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ExplicitAdaptor
////////////////////////////////////////////////////////////////////////////////
module ExplicitAdaptor (
	input logic [3:0] input_port,
	output logic [3:0] output_port
);

	assign output_port = input_port;

endmodule


