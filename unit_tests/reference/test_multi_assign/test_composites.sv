////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	output logic [7:0] outp_r,
	output logic [7:0] outp_g,
	output logic [7:0] outp_b,

	output logic [7:0] outp2_r,
	output logic [7:0] outp2_g,
	output logic [7:0] outp2_b,

	output logic [7:0] outp3_r,
	output logic [7:0] outp3_g,
	output logic [7:0] outp3_b
);

	assign outp_r = 1'h0;
	assign outp_g = 1'h1;
	assign outp_b = 2'h2;
	assign outp2_r = 5'h10;
	assign outp2_g = 5'h11;
	assign outp2_b = 5'h12;

	assign outp3_r = 8'hx;
	assign outp3_g = 8'hx;
	assign outp3_b = 8'hx;
endmodule


