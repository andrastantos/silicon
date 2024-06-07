////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	input logic inp_penable,
	output logic inp_pready,
	input logic inp_psel,
	input logic inp_pwrite,
	input logic [31:0] inp_pwdata,
	output logic [31:0] inp_prdata,
	input logic [31:0] inp_paddr,

	output logic outp_penable,
	input logic outp_pready,
	output logic outp_psel,
	output logic outp_pwrite,
	output logic [31:0] outp_pwdata,
	input logic [31:0] outp_prdata,
	output logic [31:0] outp_paddr
);

	Inner u (
		.i_inp_penable(inp_penable),
		.i_inp_pready(inp_pready),
		.i_inp_psel(inp_psel),
		.i_inp_pwrite(inp_pwrite),
		.i_inp_pwdata(inp_pwdata),
		.i_inp_prdata(inp_prdata),
		.i_inp_paddr(inp_paddr),

		.i_outp_penable(outp_penable),
		.i_outp_pready(outp_pready),
		.i_outp_psel(outp_psel),
		.i_outp_pwrite(outp_pwrite),
		.i_outp_pwdata(outp_pwdata),
		.i_outp_prdata(outp_prdata),
		.i_outp_paddr(outp_paddr)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// Inner
////////////////////////////////////////////////////////////////////////////////
module Inner (
	input logic i_inp_penable,
	output logic i_inp_pready,
	input logic i_inp_psel,
	input logic i_inp_pwrite,
	input logic [31:0] i_inp_pwdata,
	output logic [31:0] i_inp_prdata,
	input logic [31:0] i_inp_paddr,

	output logic i_outp_penable,
	input logic i_outp_pready,
	output logic i_outp_psel,
	output logic i_outp_pwrite,
	output logic [31:0] i_outp_pwdata,
	input logic [31:0] i_outp_prdata,
	output logic [31:0] i_outp_paddr
);

	assign i_outp_penable = i_inp_penable;
	assign i_outp_psel = i_inp_psel;
	assign i_outp_pwrite = i_inp_pwrite;
	assign i_outp_pwdata = i_inp_pwdata;
	assign i_outp_paddr = i_inp_paddr;
	assign i_inp_pready = i_outp_pready;
	assign i_inp_prdata = i_outp_prdata;

endmodule


