////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	output logic signed [4:0] sout1,
	input logic [1:0] uin1,
	input logic [3:0] uin2,
	input logic signed [3:0] sin1,
	input logic signed [3:0] sin2,
	input logic [1:0] sel_in
);

	logic signed [4:0] u_output_port;

	always @(*) begin
		unique case (sel_in)
			2'd0: u_output_port = uin1;
			2'd1: u_output_port = uin2;
			2'd2: u_output_port = sin1;
			2'd3: u_output_port = sin2;
		endcase
	end
	assign sout1 = u_output_port;

endmodule


