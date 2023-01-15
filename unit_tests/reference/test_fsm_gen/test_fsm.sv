////////////////////////////////////////////////////////////////////////////////
// Type definitions
////////////////////////////////////////////////////////////////////////////////
`define States__reset 3'h0
`define States__idle 3'h1
`define States__get_data 3'h2
`define States__get_wait 3'h3
`define States__get_first_data 3'h4
`define States__send_data 3'h5





////////////////////////////////////////////////////////////////////////////////
// UseFSM
////////////////////////////////////////////////////////////////////////////////
module UseFSM (
	input logic clk,
	input logic rst,
	input logic data_in_valid,
	input logic data_last,
	input logic [7:0] data_in,
	output logic [7:0] data_out,
	output logic data_out_valid
);

	logic [8:0] u30_output_port;
	logic [8:0] u35_output_port;
	logic [7:0] next_my_sum;
	logic [7:0] my_sum;
	logic [2:0] my_fsm_state;
	logic [2:0] my_fsm_next_state;

	assign next_my_sum = my_fsm_next_state == `States__reset ? 1'h0 : 8'b0 | my_fsm_next_state == `States__idle ? 1'h0 : 8'b0 | my_fsm_next_state == `States__get_first_data ? data_in : 8'b0 | my_fsm_next_state == `States__get_data ? u30_output_port[7:0] : 8'b0 | my_fsm_next_state == `States__get_wait ? my_sum : 8'b0 | my_fsm_next_state == `States__send_data ? u35_output_port[7:0] : 8'b0 ;
	always_ff @(posedge clk) my_sum <= rst ? 8'h0 : next_my_sum;
	assign data_out_valid = my_fsm_state == `States__send_data;

	FSM my_fsm (
		.clock_port(clk),
		.reset_port(rst),
		.reset_value(`States__reset),
		.state(my_fsm_state),
		.next_state(my_fsm_next_state),
		.default_state(`States__idle),
		.input_reset_to_idle(1'h1),
		.input_idle_to_get_first_data(data_in_valid &  ~ data_last),
		.input_get_data_to_get_wait( ~ data_in_valid),
		.input_get_data_to_get_data(data_in_valid &  ~ data_last),
		.input_get_wait_to_get_wait( ~ data_in_valid),
		.input_get_wait_to_get_data(data_in_valid &  ~ data_last),
		.input_get_data_to_send_data(data_in_valid & data_last),
		.input_get_wait_to_send_data(data_in_valid & data_last),
		.input_idle_to_send_data(data_in_valid & data_last),
		.input_send_data_to_idle( ~ data_in_valid),
		.input_send_data_to_get_first_data(data_in_valid &  ~ data_last),
		.input_send_data_to_send_data(data_in_valid & data_last),
		.input_get_first_data_to_get_wait( ~ data_in_valid),
		.input_get_first_data_to_get_data(data_in_valid &  ~ data_last),
		.input_get_first_data_to_send_data(data_in_valid & data_last)
	);

	assign u30_output_port = my_sum + data_in;
	assign u35_output_port = my_sum + data_in;
	assign data_out = my_sum;
endmodule


////////////////////////////////////////////////////////////////////////////////
// FSM
////////////////////////////////////////////////////////////////////////////////
module FSM (
	input logic clock_port,
	input logic reset_port,
	input logic [2:0] reset_value,
	output logic [2:0] state,
	output logic [2:0] next_state,
	input logic [2:0] default_state,
	input logic input_reset_to_idle,
	input logic input_idle_to_get_first_data,
	input logic input_get_data_to_get_wait,
	input logic input_get_data_to_get_data,
	input logic input_get_wait_to_get_wait,
	input logic input_get_wait_to_get_data,
	input logic input_get_data_to_send_data,
	input logic input_get_wait_to_send_data,
	input logic input_idle_to_send_data,
	input logic input_send_data_to_idle,
	input logic input_send_data_to_get_first_data,
	input logic input_send_data_to_send_data,
	input logic input_get_first_data_to_get_wait,
	input logic input_get_first_data_to_get_data,
	input logic input_get_first_data_to_send_data
);

	logic [2:0] local_state;
	logic [2:0] local_next_state;

	always_ff @(posedge clock_port) local_state <= reset_port ? reset_value : local_next_state;

	FSMLogic u (
		.state(local_state),
		.next_state(local_next_state),
		.default_state(default_state),
		.input_reset_to_idle(input_reset_to_idle),
		.input_idle_to_get_first_data(input_idle_to_get_first_data),
		.input_get_data_to_get_wait(input_get_data_to_get_wait),
		.input_get_data_to_get_data(input_get_data_to_get_data),
		.input_get_wait_to_get_wait(input_get_wait_to_get_wait),
		.input_get_wait_to_get_data(input_get_wait_to_get_data),
		.input_get_data_to_send_data(input_get_data_to_send_data),
		.input_get_wait_to_send_data(input_get_wait_to_send_data),
		.input_idle_to_send_data(input_idle_to_send_data),
		.input_send_data_to_idle(input_send_data_to_idle),
		.input_send_data_to_get_first_data(input_send_data_to_get_first_data),
		.input_send_data_to_send_data(input_send_data_to_send_data),
		.input_get_first_data_to_get_wait(input_get_first_data_to_get_wait),
		.input_get_first_data_to_get_data(input_get_first_data_to_get_data),
		.input_get_first_data_to_send_data(input_get_first_data_to_send_data)
	);

	assign state = local_state;
	assign next_state = local_next_state;
endmodule


////////////////////////////////////////////////////////////////////////////////
// FSMLogic
////////////////////////////////////////////////////////////////////////////////
module FSMLogic (
	input logic [2:0] state,
	output logic [2:0] next_state,
	input logic [2:0] default_state,
	input logic input_reset_to_idle,
	input logic input_idle_to_get_first_data,
	input logic input_get_data_to_get_wait,
	input logic input_get_data_to_get_data,
	input logic input_get_wait_to_get_wait,
	input logic input_get_wait_to_get_data,
	input logic input_get_data_to_send_data,
	input logic input_get_wait_to_send_data,
	input logic input_idle_to_send_data,
	input logic input_send_data_to_idle,
	input logic input_send_data_to_get_first_data,
	input logic input_send_data_to_send_data,
	input logic input_get_first_data_to_get_wait,
	input logic input_get_first_data_to_get_data,
	input logic input_get_first_data_to_send_data
);

	logic [2:0] state_reset_selector;
	logic [2:0] state_idle_selector;
	logic [2:0] state_get_data_selector;
	logic [2:0] state_get_wait_selector;
	logic [2:0] state_send_data_selector;
	logic [2:0] state_get_first_data_selector;

	assign state_reset_selector = input_reset_to_idle ? `States__idle : 3'b0 | `States__reset;
	assign state_idle_selector = input_idle_to_get_first_data ? `States__get_first_data : 3'b0 | input_idle_to_send_data ? `States__send_data : 3'b0 | `States__idle;
	assign state_get_data_selector = input_get_data_to_get_wait ? `States__get_wait : 3'b0 | input_get_data_to_get_data ? `States__get_data : 3'b0 | input_get_data_to_send_data ? `States__send_data : 3'b0 | `States__get_data;
	assign state_get_wait_selector = input_get_wait_to_get_wait ? `States__get_wait : 3'b0 | input_get_wait_to_get_data ? `States__get_data : 3'b0 | input_get_wait_to_send_data ? `States__send_data : 3'b0 | `States__get_wait;
	assign state_send_data_selector = input_send_data_to_idle ? `States__idle : 3'b0 | input_send_data_to_get_first_data ? `States__get_first_data : 3'b0 | input_send_data_to_send_data ? `States__send_data : 3'b0 | `States__send_data;
	assign state_get_first_data_selector = input_get_first_data_to_get_wait ? `States__get_wait : 3'b0 | input_get_first_data_to_get_data ? `States__get_data : 3'b0 | input_get_first_data_to_send_data ? `States__send_data : 3'b0 | `States__get_first_data;
	assign next_state = state == `States__reset ? state_reset_selector : 3'b0 | state == `States__idle ? state_idle_selector : 3'b0 | state == `States__get_data ? state_get_data_selector : 3'b0 | state == `States__get_wait ? state_get_wait_selector : 3'b0 | state == `States__send_data ? state_send_data_selector : 3'b0 | state == `States__get_first_data ? state_get_first_data_selector : 3'b0 | default_state;

endmodule


