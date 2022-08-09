////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic [7:0] a,
	output logic [7:0] o,
	output logic [7:0] p,
	output logic [7:0] q
);

	logic [5:0] u1_output_port;
	logic [8:0] u3_output_port;
	logic [7:0] u4_output_port;

	assign o = a[2];
	assign p = u1_output_port[2];
	assign q = u4_output_port[6:0];

	assign u1_output_port = a[5:0];
	assign u3_output_port = a[8:0];
	assign u4_output_port = u3_output_port[7:0];
endmodule


