////////////////////////////////////////////////////////////////////////////////
// rtl_top
////////////////////////////////////////////////////////////////////////////////
module rtl_top (
	input logic clk,
	input logic rst,
	input logic [15:0] req1_data,
	output logic req1_ready,
	input logic req1_valid,

	output logic [15:0] rsp1_data,
	input logic rsp1_ready,
	output logic rsp1_valid,

	input logic [15:0] req2_data,
	output logic req2_ready,
	input logic req2_valid,

	output logic [15:0] rsp2_data,
	input logic rsp2_ready,
	output logic rsp2_valid,

	input logic [15:0] req3_data,
	output logic req3_ready,
	input logic req3_valid,

	output logic [15:0] rsp3_data,
	input logic rsp3_ready,
	output logic rsp3_valid,

	input logic [15:0] req4_data,
	output logic req4_ready,
	input logic req4_valid,

	output logic [15:0] rsp4_data,
	input logic rsp4_ready,
	output logic rsp4_valid,

	output logic [15:0] out_req_data,
	input logic out_req_ready,
	output logic out_req_valid,

	input logic [15:0] out_rsp_data,
	output logic out_rsp_ready,
	input logic out_rsp_valid
);

	logic [1:0] dut_grant;

	GenericRVArbiter dut (
		.clk(clk),
		.rst(rst),
		.output_request_data(out_req_data),
		.output_request_ready(out_req_ready),
		.output_request_valid(out_req_valid),

		.output_response_data(out_rsp_data),
		.output_response_ready(out_rsp_ready),
		.output_response_valid(out_rsp_valid),

		.grant(dut_grant),
		.req1_request_data(req1_data),
		.req1_request_ready(req1_ready),
		.req1_request_valid(req1_valid),

		.req1_response_data(rsp1_data),
		.req1_response_ready(rsp1_ready),
		.req1_response_valid(rsp1_valid),

		.req2_request_data(req2_data),
		.req2_request_ready(req2_ready),
		.req2_request_valid(req2_valid),

		.req2_response_data(rsp2_data),
		.req2_response_ready(rsp2_ready),
		.req2_response_valid(rsp2_valid),

		.req3_request_data(req3_data),
		.req3_request_ready(req3_ready),
		.req3_request_valid(req3_valid),

		.req3_response_data(rsp3_data),
		.req3_response_ready(rsp3_ready),
		.req3_response_valid(rsp3_valid),

		.req4_request_data(req4_data),
		.req4_request_ready(req4_ready),
		.req4_request_valid(req4_valid),

		.req4_response_data(rsp4_data),
		.req4_response_ready(rsp4_ready),
		.req4_response_valid(rsp4_valid)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// GenericRVArbiter
////////////////////////////////////////////////////////////////////////////////
module GenericRVArbiter (
	input logic clk,
	input logic rst,
	output logic [15:0] output_request_data,
	input logic output_request_ready,
	output logic output_request_valid,

	input logic [15:0] output_response_data,
	output logic output_response_ready,
	input logic output_response_valid,

	output logic [1:0] grant,
	input logic [15:0] req1_request_data,
	output logic req1_request_ready,
	input logic req1_request_valid,

	output logic [15:0] req1_response_data,
	input logic req1_response_ready,
	output logic req1_response_valid,

	input logic [15:0] req2_request_data,
	output logic req2_request_ready,
	input logic req2_request_valid,

	output logic [15:0] req2_response_data,
	input logic req2_response_ready,
	output logic req2_response_valid,

	input logic [15:0] req3_request_data,
	output logic req3_request_ready,
	input logic req3_request_valid,

	output logic [15:0] req3_response_data,
	input logic req3_response_ready,
	output logic req3_response_valid,

	input logic [15:0] req4_request_data,
	output logic req4_request_ready,
	input logic req4_request_valid,

	output logic [15:0] req4_response_data,
	input logic req4_response_ready,
	output logic req4_response_valid
);

	logic request_progress;
	logic selector_fifo_output_ready;
	logic response_progress;
	logic u5_output_port;
	logic u7_output_port;
	logic selector_fifo_input_valid;
	logic req_port_ready;
	logic rsp_port_valid;
	logic [15:0] rsp_port_data;
	logic selector_fifo_input_ready;
	logic selector_fifo_output_valid;
	logic [1:0] selector_fifo_output_data;
	logic [1:0] response_port;
	logic u59_output_port;
	logic [1:0] selector_fifo_input_data;
	logic [1:0] selected_port;
	logic u61_output_port;
	logic [3:0] binary_requestors;

	assign request_progress = output_request_ready & output_request_valid & selector_fifo_input_ready;
	assign response_progress = output_response_ready & output_response_valid;
	always @(*) begin
		unique case (selected_port)
			2'd0: output_request_data = req1_request_data;
			2'd1: output_request_data = req2_request_data;
			2'd2: output_request_data = req3_request_data;
			2'd3: output_request_data = req4_request_data;
			default: output_request_data = 16'hx;
		endcase
	end
	always @(*) begin
		unique case (selected_port)
			2'd0: u5_output_port = req1_request_valid;
			2'd1: u5_output_port = req2_request_valid;
			2'd2: u5_output_port = req3_request_valid;
			2'd3: u5_output_port = req4_request_valid;
			default: u5_output_port = 1'hx;
		endcase
	end
	assign output_request_valid = u5_output_port & selector_fifo_input_ready;
	always @(*) begin
		unique case (selected_port)
			2'd0: u7_output_port = req1_request_valid;
			2'd1: u7_output_port = req2_request_valid;
			2'd2: u7_output_port = req3_request_valid;
			2'd3: u7_output_port = req4_request_valid;
			default: u7_output_port = 1'hx;
		endcase
	end
	assign selector_fifo_input_valid = u7_output_port & output_request_ready;
	assign req1_request_ready = selected_port == 1'h0 ? output_request_ready & selector_fifo_input_ready : 1'h0;
	assign req2_request_ready = selected_port == 1'h1 ? output_request_ready & selector_fifo_input_ready : 1'h0;
	assign req3_request_ready = selected_port == 2'h2 ? output_request_ready & selector_fifo_input_ready : 1'h0;
	assign req_port_ready = selected_port == 2'h3 ? output_request_ready & selector_fifo_input_ready : 1'h0;
	assign req1_response_valid = (response_port == 1'h0 & selector_fifo_output_valid) ? output_response_valid : 1'h0;
	assign req2_response_valid = (response_port == 1'h1 & selector_fifo_output_valid) ? output_response_valid : 1'h0;
	assign req3_response_valid = (response_port == 2'h2 & selector_fifo_output_valid) ? output_response_valid : 1'h0;
	assign rsp_port_valid = (response_port == 2'h3 & selector_fifo_output_valid) ? output_response_valid : 1'h0;
	always @(*) begin
		unique case (response_port)
			2'd0: output_response_ready = req1_response_ready;
			2'd1: output_response_ready = req2_response_ready;
			2'd2: output_response_ready = req3_response_ready;
			2'd3: output_response_ready = req4_response_ready;
			default: output_response_ready = 1'hx;
		endcase
	end
	assign binary_requestors = {req4_request_valid, req3_request_valid, req2_request_valid, req1_request_valid};
	assign req1_response_data = output_response_data;
	assign req2_response_data = output_response_data;
	assign req3_response_data = output_response_data;
	assign rsp_port_data = output_response_data;

	Fifo u (
		.input_port_ready(selector_fifo_input_ready),
		.input_port_valid(selector_fifo_input_valid),
		.input_port_data(selected_port),

		.output_port_ready(response_progress),
		.output_port_valid(selector_fifo_output_valid),
		.output_port_data(response_port),

		.clock_port(clk),
		.reset_port(rst),
		.clear(u59_output_port)
	);

	RoundRobinArbiter arbiter_logic (
		.clk(clk),
		.rst(rst),
		.requestors(binary_requestors),
		.grant(selected_port),
		.advance(request_progress),
		.restart(u61_output_port)
	);

	GenericAssertOnClk u52 (
		.clk(clk),
		.rst(rst),
		.input_port(selector_fifo_output_valid |  ~ output_response_valid)
	);

	assign selector_fifo_output_ready = response_progress;
	assign req4_request_ready = req_port_ready;
	assign req4_response_valid = rsp_port_valid;
	assign req4_response_data = rsp_port_data;
	assign selector_fifo_output_data = response_port;
	assign u59_output_port = 1'h0;
	assign grant = selected_port;
	assign selector_fifo_input_data = selected_port;
	assign u61_output_port = 1'h0;
endmodule


////////////////////////////////////////////////////////////////////////////////
// GenericAssertOnClk
////////////////////////////////////////////////////////////////////////////////
module GenericAssertOnClk (
	input logic clk,
	input logic rst,
	input logic input_port
);

endmodule


////////////////////////////////////////////////////////////////////////////////
// RoundRobinArbiter
////////////////////////////////////////////////////////////////////////////////
module RoundRobinArbiter (
	input logic clk,
	input logic rst,
	input logic [3:0] requestors,
	output logic [1:0] grant,
	input logic advance,
	input logic restart
);

	logic [2:0] next_mask;
	logic [2:0] mask;
	logic [3:0] masked_requestors;
	logic [1:0] masked_selector;
	logic use_masked_selector;
	logic [1:0] unmasked_selector;

	assign next_mask = mask[0] ? 1'h0 : mask >> 1'h1 | 3'h4;
	always_ff @(posedge clk) mask <= rst ? 3'h0 : restart ? 1'h0 : advance ? next_mask : mask;
	assign masked_requestors = requestors &  ~ ({mask, 1'h0});
	assign use_masked_selector = masked_requestors[3] ? 1'h1 : masked_requestors[2] ? 1'h1 : masked_requestors[1] ? 1'h1 : masked_requestors[0] ? 1'h1 : 1'h0;
	assign unmasked_selector = requestors[3] ? 2'h3 : requestors[2] ? 2'h2 : requestors[1] ? 1'h1 : requestors[0] ? 1'h0 : 1'h0;
	assign masked_selector = masked_requestors[3] ? 2'h3 : masked_requestors[2] ? 2'h2 : masked_requestors[1] ? 1'h1 : masked_requestors[0] ? 1'h0 : 1'h0;
	assign grant = use_masked_selector ? masked_selector : unmasked_selector;

endmodule


////////////////////////////////////////////////////////////////////////////////
// Fifo
////////////////////////////////////////////////////////////////////////////////
module Fifo (
	output logic input_port_ready,
	input logic input_port_valid,
	input logic [1:0] input_port_data,

	input logic output_port_ready,
	output logic output_port_valid,
	output logic [1:0] output_port_data,

	input logic clock_port,
	input logic reset_port,
	input logic clear
);

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
	logic [1:0] reg_in_data_data;
	logic u94_output_port;
	logic out_data_selector;
	logic [1:0] output_data_data;
	logic [1:0] buffer_mem_port2_data_out_data;
	logic [3:0] incremented_pop_addr;
	logic [1:0] input_data_data;

	assign input_port_ready =  ~ full;
	assign output_port_valid =  ~ empty;
	assign push_will_wrap = push_addr == 4'h9;
	assign push =  ~ full & input_port_valid;
	assign next_push_addr = push ? push_will_wrap ? 1'h0 : push_addr + 1'h1 : push_addr;
	assign pop_will_wrap = pop_addr == 4'h9;
	assign pop =  ~ empty & output_port_ready;
	assign incremented_pop_addr = pop_will_wrap ? 1'h0 : pop_addr + 1'h1;
	assign next_pop_addr = pop ? incremented_pop_addr : pop_addr;
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
	assign out_data_selector = push_addr == incremented_pop_addr & u94_output_port;
	always_ff @(posedge clock_port) reg_in_data_data <= reset_port ? 2'h0 : input_port_data;
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

	assign output_port_data = output_data_data;
	assign input_data_data = input_port_data;
endmodule


////////////////////////////////////////////////////////////////////////////////
// Memory
////////////////////////////////////////////////////////////////////////////////
module Memory (
	input logic [3:0] port1_addr,
	input logic port1_clk,
	input logic [3:0] port2_addr,
	input logic port2_clk,
	input logic [1:0] port1_data_in_data,
	input logic port1_write_en,
	output logic [1:0] port2_data_out_data
);

	logic [1:0] real_mem_port2_data_out;

	reg [1:0] mem [0:15];

	always @(posedge port1_clk) begin
		if (port1_write_en) begin
			mem[port1_addr] <= {port1_data_in_data};
		end
	end

	always @(posedge port1_clk) begin
		real_mem_port2_data_out <= mem[port2_addr];
	end

	assign {port2_data_out_data} = real_mem_port2_data_out;

endmodule


