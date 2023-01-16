////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
);

	logic in_if_in_if_member;
	logic mem_to_bus_out_if1_member;
	logic out_if2_out_if2_member;

	Producer producer (
		.in_if_in_if_member(in_if_in_if_member)
	);

	Consumer consumer (
		.consumer_in_in_if_member(in_if_in_if_member),

		.consumer_out1_out_if1_member(mem_to_bus_out_if1_member),

		.consumer_out2_out_if2_member(out_if2_out_if2_member)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// Consumer
////////////////////////////////////////////////////////////////////////////////
module Consumer (
	input logic consumer_in_in_if_member,
	output logic consumer_out1_out_if1_member,
	output logic consumer_out2_out_if2_member
);

	assign consumer_out1_out_if1_member = consumer_in_in_if_member;
	assign consumer_out2_out_if2_member = consumer_in_in_if_member;

endmodule


////////////////////////////////////////////////////////////////////////////////
// Producer
////////////////////////////////////////////////////////////////////////////////
module Producer (
	output logic in_if_in_if_member
);

	assign in_if_in_if_member = 1'h1;

endmodule


