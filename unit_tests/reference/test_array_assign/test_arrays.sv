////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic [7:0] out_port_element_0,
	output logic [7:0] out_port_element_1,
	output logic [7:0] out_port_element_2,
	output logic [7:0] out_port_element_3,

	input logic [7:0] in1_element_0,
	input logic [7:0] in1_element_1,
	input logic [7:0] in1_element_2,
	input logic [7:0] in1_element_3
);

	assign out_port_element_0 = in1_element_0;
	assign out_port_element_1 = in1_element_1;
	assign out_port_element_2 = in1_element_2;
	assign out_port_element_3 = in1_element_3;
endmodule


