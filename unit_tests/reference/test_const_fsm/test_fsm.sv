////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic clk,
	input logic rst
);

	logic u3_output_port;
	logic [3:0] u_state;
	logic [3:0] shouldnt_matter;

	FSM u (
		.clock_port(clk),
		.reset_port(rst),
		.reset_value(4'hb),
		.state(u_state),
		.next_state(shouldnt_matter),
		.default_state(4'hc),
		.input_11_to_12(u3_output_port)
	);

	assign u3_output_port = 1'h1;
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

	logic [3:0] local_state;
	logic [3:0] u_next_state;
	logic [3:0] local_next_state;

	always_ff @(posedge clock_port) local_state <= reset_port ? reset_value : local_next_state;
	assign local_next_state = u_next_state;

	FSMLogic u (
		.state(local_state),
		.next_state(u_next_state),
		.default_state(default_state),
		.input_11_to_12(input_11_to_12)
	);

	assign state = local_state;
	assign next_state = local_next_state;
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

	logic condition_port;
	logic [3:0] condition_selector;

	assign condition_selector = input_11_to_12 ? 4'hc : 4'b0 | default_state;
	assign next_state = state == 4'hb ? condition_selector : 4'b0 | default_state;

	assign condition_port = input_11_to_12;
endmodule


