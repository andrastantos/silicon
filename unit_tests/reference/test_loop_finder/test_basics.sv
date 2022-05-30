////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic clk,
	input logic rst
);

	logic [1:0] u2_next_state;
	logic [1:0] u2_state;
	logic aaa;
	logic ddd;

	assign aaa = u2_state == 1'h0;
	assign ddd = u2_state == 1'h0;

	FSM u2 (
		.clock_port(clk),
		.reset_port(rst),
		.reset_value(1'h0),
		.state(u2_state),
		.next_state(u2_next_state),
		.default_state(1'h0),
		.input_0_to_1(aaa),
		.input_0_to_3(ddd)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// FSM
////////////////////////////////////////////////////////////////////////////////
module FSM (
	input logic clock_port,
	input logic reset_port,
	input logic reset_value,
	output logic [1:0] state,
	output logic [1:0] next_state,
	input logic default_state,
	input logic input_0_to_1,
	input logic input_0_to_3
);

	logic [1:0] local_next_state;
	logic [1:0] local_state;

	always_ff @(posedge clock_port) local_state <= reset_port ? reset_value : local_next_state;

	FSMLogic u (
		.state(local_state),
		.next_state(local_next_state),
		.default_state(default_state),
		.input_0_to_1(input_0_to_1),
		.input_0_to_3(input_0_to_3)
	);

	assign next_state = local_next_state;
	assign state = local_state;
endmodule


////////////////////////////////////////////////////////////////////////////////
// FSMLogic
////////////////////////////////////////////////////////////////////////////////
module FSMLogic (
	input logic [1:0] state,
	output logic [1:0] next_state,
	input logic default_state,
	input logic input_0_to_1,
	input logic input_0_to_3
);

	logic [1:0] condition_selector;
	logic condition_port;

	assign condition_selector = input_0_to_1 ? 1'h1 : 2'b0 | input_0_to_3 ? 2'h3 : 2'b0 | default_state;
	assign next_state = state == 1'h0 ? condition_selector : 2'b0 | default_state;

	assign condition_port = input_0_to_3;
endmodule


