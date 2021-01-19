////////////////////////////////////////////////////////////////////////////////
// Type definitions
////////////////////////////////////////////////////////////////////////////////
typedef enum logic [2:0] {
	reset=0,
	idle=1,
	get_data=2,
	get_wait=3,
	get_first_data=4,
	send_data=5
} States;




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

	States my_fsm_next_state;
	States my_fsm_state;
	logic [7:0] next_my_sum;
	logic [7:0] my_sum;

	assign next_my_sum = my_fsm_next_state == reset ? 1'h0 : 8'b0 | my_fsm_next_state == idle ? 1'h0 : 8'b0 | my_fsm_next_state == get_first_data ? data_in : 8'b0 | my_fsm_next_state == get_data ? (my_sum + data_in)[7:0] : 8'b0 | my_fsm_next_state == get_wait ? my_sum : 8'b0 | my_fsm_next_state == send_data ? (my_sum + data_in)[7:0] : 8'b0 | 'X;
	always_ff @(posedge clk) my_sum <= rst ? 8'b0 : next_my_sum;
	assign data_out_valid = my_fsm_state == send_data;

	FSM my_fsm (
		.clock_port(clk),
		.reset_port(rst),
		.reset_value(reset),
		.state(my_fsm_state),
		.next_state(my_fsm_next_state),
		.default_state(idle),
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

	assign data_out = my_sum;
endmodule


////////////////////////////////////////////////////////////////////////////////
// FSM
////////////////////////////////////////////////////////////////////////////////
module FSM (
	input logic clock_port,
	input logic reset_port,
	input States reset_value,
	output States state,
	output States next_state,
	input States default_state,
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

	States local_next_state;
	States local_state;

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

	assign next_state = local_next_state;
	assign state = local_state;
endmodule


////////////////////////////////////////////////////////////////////////////////
// FSMLogic
////////////////////////////////////////////////////////////////////////////////
module FSMLogic (
	input States state,
	output States next_state,
	input States default_state,
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

	logic condition_port;
	States condition_selector;

	assign condition_selector = input_get_first_data_to_get_wait ? get_wait : 3'b0 | input_get_first_data_to_get_data ? get_data : 3'b0 | input_get_first_data_to_send_data ? send_data : 3'b0 | default_state;
	assign next_state = state == reset ? input_reset_to_idle ? idle : 3'b0 | default_state : 3'b0 | state == idle ? input_idle_to_get_first_data ? get_first_data : 3'b0 | input_idle_to_send_data ? send_data : 3'b0 | default_state : 3'b0 | state == get_data ? input_get_data_to_get_wait ? get_wait : 3'b0 | input_get_data_to_get_data ? get_data : 3'b0 | input_get_data_to_send_data ? send_data : 3'b0 | default_state : 3'b0 | state == get_wait ? input_get_wait_to_get_wait ? get_wait : 3'b0 | input_get_wait_to_get_data ? get_data : 3'b0 | input_get_wait_to_send_data ? send_data : 3'b0 | default_state : 3'b0 | state == send_data ? input_send_data_to_idle ? idle : 3'b0 | input_send_data_to_get_first_data ? get_first_data : 3'b0 | input_send_data_to_send_data ? send_data : 3'b0 | default_state : 3'b0 | state == get_first_data ? condition_selector : 3'b0 | default_state;

	assign condition_port = input_get_first_data_to_send_data;
endmodule


