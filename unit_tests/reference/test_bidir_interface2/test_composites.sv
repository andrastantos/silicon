////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic top_out_bwd
);

	logic top_w_bwd;

	mod m (
		.mod_out_bwd(top_out_bwd)
	);

	assign top_w_bwd = top_out_bwd;
endmodule


////////////////////////////////////////////////////////////////////////////////
// mod
////////////////////////////////////////////////////////////////////////////////
module mod (
	input logic mod_out_bwd
);

endmodule

