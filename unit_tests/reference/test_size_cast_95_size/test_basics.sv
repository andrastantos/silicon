////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic [7:0] i1,
	input logic [7:0] i2,
	input logic [1:0] i3,
	output logic [13:0] o,
	output logic [13:0] o2,
	output logic [13:0] o3
);

	logic [9:0] prod;

	assign o = i2 * i1 + 16'b0 >> i3;
	assign o2 = (i2 * i1 + 16'b0) * i3 + 18'b0 >> i3;
	assign prod = i2 * i3;
	assign o3 = prod * i1 + 18'b0 >> i3;

endmodule


