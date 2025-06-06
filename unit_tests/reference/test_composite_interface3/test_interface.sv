////////////////////////////////////////////////////////////////////////////////
// top
////////////////////////////////////////////////////////////////////////////////
module top (
	input logic [7:0] side_a_addr_read_bus_data,
	output logic side_a_addr_read_bus_ready,
	input logic side_a_addr_read_bus_valid,
	input logic [7:0] side_a_addr_write_bus_data,
	output logic side_a_addr_write_bus_ready,
	input logic side_a_addr_write_bus_valid,
	output logic [7:0] side_a_data_read_bus_data,
	input logic side_a_data_read_bus_ready,
	output logic side_a_data_read_bus_valid,
	input logic [7:0] side_a_data_write_bus_data,
	output logic side_a_data_write_bus_ready,
	input logic side_a_data_write_bus_valid,
	output logic [7:0] side_a_resp_write_bus_data,
	input logic side_a_resp_write_bus_ready,
	output logic side_a_resp_write_bus_valid,

	output logic [7:0] side_b_addr_read_bus_data,
	input logic side_b_addr_read_bus_ready,
	output logic side_b_addr_read_bus_valid,
	output logic [7:0] side_b_addr_write_bus_data,
	input logic side_b_addr_write_bus_ready,
	output logic side_b_addr_write_bus_valid,
	input logic [7:0] side_b_data_read_bus_data,
	output logic side_b_data_read_bus_ready,
	input logic side_b_data_read_bus_valid,
	output logic [7:0] side_b_data_write_bus_data,
	input logic side_b_data_write_bus_ready,
	output logic side_b_data_write_bus_valid,
	input logic [7:0] side_b_resp_write_bus_data,
	output logic side_b_resp_write_bus_ready,
	input logic side_b_resp_write_bus_valid
);

	assign side_b_addr_write_bus_data = side_a_addr_write_bus_data;
	assign side_b_addr_write_bus_valid = side_a_addr_write_bus_valid;
	assign side_a_addr_write_bus_ready = side_b_addr_write_bus_ready;

	assign side_a_addr_read_bus_ready = 1'hx;
	assign side_a_data_read_bus_data = 8'hx;
	assign side_a_data_read_bus_valid = 1'hx;
	assign side_a_data_write_bus_ready = 1'hx;
	assign side_a_resp_write_bus_data = 8'hx;
	assign side_a_resp_write_bus_valid = 1'hx;
	assign side_b_addr_read_bus_data = 8'hx;
	assign side_b_addr_read_bus_valid = 1'hx;
	assign side_b_data_read_bus_ready = 1'hx;
	assign side_b_data_write_bus_data = 8'hx;
	assign side_b_data_write_bus_valid = 1'hx;
	assign side_b_resp_write_bus_ready = 1'hx;
endmodule


