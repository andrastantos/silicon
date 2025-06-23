////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic [3:0] input_port,
	output logic output1,
	output logic output2
);

	OneHotDecode decoder (
		.input_port(input_port),
		.output_for_0(output1),
		.output_for_5(output2)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// OneHotDecode
////////////////////////////////////////////////////////////////////////////////
module OneHotDecode (
	input logic [3:0] input_port,
	output logic output_for_0,
	output logic output_for_5
);

	logic [3:0] in_val;
	logic [3:0] in_val_n;
	logic out_1;

	assign in_val_n =  ~ input_port;
	assign output_for_0 = in_val_n[0] & in_val_n[1] & in_val_n[2] & in_val_n[3];
	assign out_1 = input_port[0] & in_val_n[1] & input_port[2] & in_val_n[3];

	assign in_val = input_port;
	assign output_for_5 = out_1;
endmodule


