struct packed {
	bit [7:0] A;
	bit [7:0] B;
	byte C;
} abc;

nettype abc wabc;

module verilog_tests(
	input wabc in1,
	input logic [7:0] in2,
	input logic [7:0] in3,
	output logic [7:0] out
);
  assign out = in1 & in2 | in3;
endmodule
