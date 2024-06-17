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

	logic u1_output_port;

	ZeroDelayFifo dut (
		.input_port_data(in1_data),
		.input_port_ready(in1_ready),
		.input_port_valid(in1_valid),

		.output_port_data(out1_data),
		.output_port_ready(out1_ready),
		.output_port_valid(out1_valid),

		.clock_port(clk),
		.reset_port(rst),
		.clear(u1_output_port)
	);

	assign u1_output_port = 1'h0;
endmodule


////////////////////////////////////////////////////////////////////////////////
// ZeroDelayFifo
////////////////////////////////////////////////////////////////////////////////
module ZeroDelayFifo (
	input logic [7:0] input_port_data,
	output logic input_port_ready,
	input logic input_port_valid,

	output logic [7:0] output_port_data,
	input logic output_port_ready,
	output logic output_port_valid,

	input logic clock_port,
	input logic reset_port,
	input logic clear
);

	logic [7:0] data_data;
	logic [7:0] fifo_input_data;
	logic fifo_output_ready;
	logic fifo_empty;
	logic bypass;
	logic fifo_input_valid;
	logic [7:0] out_data_data;
	logic fifo_input_ready;
	logic fifo_output_valid;
	logic [7:0] fifo_output_data;

	assign fifo_empty =  ~ fifo_output_valid;
	assign bypass = fifo_empty & output_port_ready & input_port_valid &  ~ clear;
	assign fifo_input_valid =  ~ bypass & input_port_valid;
	assign output_port_valid = bypass | fifo_output_valid;
	assign out_data_data = bypass ? input_port_data : fifo_output_data;

	Fifo fifo (
		.input_port_data(input_port_data),
		.input_port_ready(fifo_input_ready),
		.input_port_valid(fifo_input_valid),

		.output_port_data(fifo_output_data),
		.output_port_ready(output_port_ready),
		.output_port_valid(fifo_output_valid),

		.clock_port(clock_port),
		.reset_port(reset_port),
		.clear(clear)
	);

	assign data_data = input_port_data;
	assign fifo_input_data = input_port_data;
	assign fifo_output_ready = output_port_ready;
	assign output_port_data = out_data_data;
	assign input_port_ready = fifo_input_ready;
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
	input logic reset_port,
	input logic clear
);

	logic [7:0] input_data_data;
	logic push;
	logic pop;
	logic push_will_wrap;
	logic pop_will_wrap;
	logic [3:0] next_push_addr;
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
	logic [7:0] reg_in_data_data;
	logic u94_output_port;
	logic out_data_selector;
	logic [7:0] output_data_data;
	logic [7:0] buffer_mem_port2_data_out_data;

	assign input_port_ready =  ~ full;
	assign output_port_valid =  ~ empty;
	assign push_will_wrap = push_addr == 4'h9;
	assign push =  ~ full & input_port_valid;
	assign next_push_addr = push ? push_will_wrap ? 1'h0 : push_addr + 1'h1 : push_addr;
	assign pop_will_wrap = pop_addr == 4'h9;
	assign pop =  ~ empty & output_port_ready;
	assign next_pop_addr = pop ? pop_will_wrap ? 1'h0 : pop_addr + 1'h1 : pop_addr;
	assign next_looped = 
		(push != 1'h1 & pop != 1'h1 ? looped : 1'b0) | 
		(push == 1'h1 & pop != 1'h1 ? push_will_wrap ? 1'h1 : looped : 1'b0) | 
		(push != 1'h1 & pop == 1'h1 ? pop_will_wrap ? 1'h0 : looped : 1'b0) | 
		(push == 1'h1 & pop == 1'h1 ? 
		(push_will_wrap != 1'h1 & pop_will_wrap != 1'h1 ? looped : 1'b0) | 
		(push_will_wrap == 1'h1 & pop_will_wrap != 1'h1 ? 1'h1 : 1'b0) | 
		(push_will_wrap != 1'h1 & pop_will_wrap == 1'h1 ? 1'h0 : 1'b0) | 
		(push_will_wrap == 1'h1 & pop_will_wrap == 1'h1 ? looped : 1'b0)  : 1'b0) ;
	assign next_empty_or_full = next_push_addr == next_pop_addr;
	assign next_empty = next_empty_or_full ?  ~ next_looped : 1'h0;
	assign next_full = next_empty_or_full ? next_looped : 1'h0;
	always_ff @(posedge clock_port) push_addr <= reset_port ? 4'h0 : clear ? 1'h0 : next_push_addr;
	always_ff @(posedge clock_port) pop_addr <= reset_port ? 4'h0 : clear ? 1'h0 : next_pop_addr;
	always_ff @(posedge clock_port) empty <= reset_port ? 1'h1 : clear ? 1'h1 : next_empty;
	initial empty <= 1'h1;
	always_ff @(posedge clock_port) full <= reset_port ? 1'h0 : clear ? 1'h0 : next_full;
	always_ff @(posedge clock_port) looped <= reset_port ? 1'h0 : clear ? 1'h0 : next_looped;
	always_ff @(posedge clock_port) u94_output_port <= reset_port ? 1'h0 : push;
	assign out_data_selector = push_addr == next_pop_addr & u94_output_port;
	always_ff @(posedge clock_port) reg_in_data_data <= reset_port ? 8'h0 : input_port_data;
	assign output_data_data = out_data_selector ? reg_in_data_data : buffer_mem_port2_data_out_data;

	Memory buffer_mem (
		.port1_addr(push_addr),
		.port1_clk(clock_port),
		.port2_addr(next_pop_addr),
		.port2_clk(clock_port),
		.port1_data_in_data(input_port_data),

		.port1_write_en(push),
		.port2_data_out_data(buffer_mem_port2_data_out_data)
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

	reg [7:0] mem [0:15];

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


