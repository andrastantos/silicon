////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic [7:0] a,
	output logic [7:0] o,
	output logic [7:0] p,
	output logic [7:0] q
);

	logic [5:0] u2_output_port;
	logic [7:0] u5_output_port;
	logic [6:0] u4_output_port;

	assign o = a[2];
	assign p = u2_output_port[2];
	assign q = u4_output_port[5:0];

	assign u2_output_port = a[5:0];
	assign u5_output_port = a[7:0];
	assign u4_output_port = u5_output_port[6:0];
endmodule


