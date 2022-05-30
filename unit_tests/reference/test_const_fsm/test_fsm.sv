////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic clk,
	input logic rst
);

	logic [3:0] shouldnt_matter;
	logic [3:0] u2_state;
	logic unnamed_wire_1;

	FSM u2 (
		.clock_port(clk),
		.reset_port(rst),
		.reset_value(4'hb),
		.state(u2_state),
		.next_state(shouldnt_matter),
		.default_state(4'hc),
		.input_11_to_12(unnamed_wire_1)
	);

	assign unnamed_wire_1 = 1'h1;
endmodule


////////////////////////////////////////////////////////////////////////////////
// FSM
////////////////////////////////////////////////////////////////////////////////
module FSM (
	input logic clock_port,
	input logic reset_port,
	input logic [3:0] reset_value,
	output logic [3:0] state,
	output logic [3:0] next_state,
	input logic [3:0] default_state,
	input logic input_11_to_12
);

	logic [3:0] local_next_state;
	logic [3:0] local_state;

	always_ff @(posedge clock_port) local_state <= reset_port ? reset_value : local_next_state;

	FSMLogic u (
		.state(local_state),
		.next_state(local_next_state),
		.default_state(default_state),
		.input_11_to_12(input_11_to_12)
	);

	assign next_state = local_next_state;
	assign state = local_state;
endmodule


////////////////////////////////////////////////////////////////////////////////
// FSMLogic
////////////////////////////////////////////////////////////////////////////////
module FSMLogic (
	input logic [3:0] state,
	output logic [3:0] next_state,
	input logic [3:0] default_state,
	input logic input_11_to_12
);

	logic [3:0] condition_selector;
	logic condition_port;

	assign condition_selector = input_11_to_12 ? 4'hc : 4'b0 | default_state;
	assign next_state = state == 4'hb ? condition_selector : 4'b0 | default_state;

	assign condition_port = input_11_to_12;
endmodule


