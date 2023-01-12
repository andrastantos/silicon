////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic signed [4:0] uout1,
	input logic [3:0] uin2,
	input logic clk
);

	logic [3:0] registered;
	logic signed [4:0] registered_1;

	always_ff @(posedge clk) registered <= uin2;
	assign registered_1 = registered;

	assign uout1 = registered_1;
endmodule


