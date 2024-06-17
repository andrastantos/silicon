////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
);
    logic [13:0] data_in_a;
    logic [13:0] data_out_a;
    logic [13:0] data_in_b;
    logic [13:0] data_out_b;
    logic [5:0] addr_a;
    logic [5:0] addr_b;
    logic write_en_a;
    logic write_en_b;
    logic clk;
    logic rst;

	Memory mem (
		.port1_addr(addr_a),
		.port1_clk(clk),
		.port2_addr(addr_b),
		.port2_clk(clk),
		.port1_data_out(data_out_a),
		.port1_data_in(data_in_a),
		.port1_write_en(write_en_a),
		.port2_data_out(data_out_b),
		.port2_data_in(data_in_b),
		.port2_write_en(write_en_b)
	);


    initial begin
        clk = 1;
    end

    always #5 clk = ~clk;

    initial begin
        $display("Reset applied");
        rst = 1;
        #50;
        rst = 0;
        $display("Reset removed");
        //#30006 n_rst = 0;
        //#28660 n_rst = 0;
        //$display("Reset applied");
        //#30104 n_rst = 1;
        //$display("Reset removed");
    end

    logic [5:0] phase;
    always @(posedge clk) begin
        if (rst == 0) begin
            if (phase == 0) begin
                write_en_a <= 1;
                addr_a <= addr_a + 1'b1;
                data_in_a <= data_in_a + 1'b1;
                write_en_b <= 0;
                addr_b <= addr_b + 1'b1;
                if (addr_a == 16) phase <= phase + 1;
            end else begin
                if (phase == 1) begin
                    write_en_a <= 0;
                    addr_a <= addr_a + 1'b1;
                    write_en_b <= 1;
                    addr_b <= addr_b + 1'b1;
                    data_in_b <= data_in_b + 1'b1;
                    if (addr_a == 16) phase <= phase + 1;
                end else begin
                    if (phase == 2) begin
                        $finish;
                    end
                end
            end
        end else begin
            addr_a <= 0;
            addr_b <= 0;
            write_en_a <= 0;
            write_en_b <= 0;
            data_in_a <= 256;
            data_in_b <= 512;
            phase <= 0;
        end
    end

    initial begin
        $dumpfile("test_memory.vcd");
        $dumpvars(0,mem);
        #(1000);
        $display("Timeout on simulation");
        $finish;
    end

endmodule


////////////////////////////////////////////////////////////////////////////////
// Memory
////////////////////////////////////////////////////////////////////////////////
module Memory (
	input logic [5:0] port1_addr,
	input logic port1_clk,
	input logic [5:0] port2_addr,
	input logic port2_clk,
	output logic [13:0] port1_data_out,
	input logic [13:0] port1_data_in,
	input logic port1_write_en,
	output logic [13:0] port2_data_out,
	input logic [13:0] port2_data_in,
	input logic port2_write_en
);

	reg [13:0] mem [0:63];

	initial begin
		$readmemh("config.bin", mem);
	end

	logic [5:0] port1_addr_reg;
	always @(posedge port1_clk) begin
		if (port1_write_en) begin
			mem[port1_addr] <= port1_data_in;
		end
		port1_addr_reg <= port1_addr;
	end
	assign port1_data_out = mem[port1_addr_reg];

	logic [5:0] port2_addr_reg;
	always @(posedge port1_clk) begin
		if (port2_write_en) begin
			mem[port2_addr] <= port2_data_in;
		end
		port2_addr_reg <= port2_addr;
	end
	assign port2_data_out = mem[port2_addr_reg];


endmodule


