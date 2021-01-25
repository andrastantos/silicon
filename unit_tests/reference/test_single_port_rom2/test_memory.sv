////////////////////////////////////////////////////////////////////////////////
// Top
////////////////////////////////////////////////////////////////////////////////
module Top (
	output logic [7:0] data_out,
	input logic [7:0] addr,
	input logic clk
);

	Memory mem (
		.addr(addr),
		.clk(clk),
		.data_out(data_out)
	);

endmodule


////////////////////////////////////////////////////////////////////////////////
// Memory
////////////////////////////////////////////////////////////////////////////////
module Memory (
	input logic [7:0] addr,
	input logic clk,
	output logic [7:0] data_out
);

	wire [7:0] mem [255:0];
	initial begin
		mem[0] <= 8'h0;
		mem[1] <= 8'h1;
		mem[2] <= 8'h2;
		mem[3] <= 8'h3;
		mem[4] <= 8'h4;
		mem[5] <= 8'h5;
		mem[6] <= 8'h6;
		mem[7] <= 8'h7;
		mem[8] <= 8'h8;
		mem[9] <= 8'h9;
		mem[10] <= 8'ha;
		mem[11] <= 8'hb;
		mem[12] <= 8'hc;
		mem[13] <= 8'hd;
		mem[14] <= 8'he;
		mem[15] <= 8'hf;
		mem[16] <= 8'h10;
		mem[17] <= 8'h11;
		mem[18] <= 8'h12;
		mem[19] <= 8'h13;
		mem[20] <= 8'h14;
		mem[21] <= 8'h15;
		mem[22] <= 8'h16;
		mem[23] <= 8'h17;
		mem[24] <= 8'h18;
		mem[25] <= 8'h19;
		mem[26] <= 8'h1a;
		mem[27] <= 8'h1b;
		mem[28] <= 8'h1c;
		mem[29] <= 8'h1d;
		mem[30] <= 8'h1e;
		mem[31] <= 8'h1f;
		mem[32] <= 8'h20;
		mem[33] <= 8'h21;
		mem[34] <= 8'h22;
		mem[35] <= 8'h23;
		mem[36] <= 8'h24;
		mem[37] <= 8'h25;
		mem[38] <= 8'h26;
		mem[39] <= 8'h27;
		mem[40] <= 8'h28;
		mem[41] <= 8'h29;
		mem[42] <= 8'h2a;
		mem[43] <= 8'h2b;
		mem[44] <= 8'h2c;
		mem[45] <= 8'h2d;
		mem[46] <= 8'h2e;
		mem[47] <= 8'h2f;
		mem[48] <= 8'h30;
		mem[49] <= 8'h31;
		mem[50] <= 8'h32;
		mem[51] <= 8'h33;
		mem[52] <= 8'h34;
		mem[53] <= 8'h35;
		mem[54] <= 8'h36;
		mem[55] <= 8'h37;
		mem[56] <= 8'h38;
		mem[57] <= 8'h39;
		mem[58] <= 8'h3a;
		mem[59] <= 8'h3b;
		mem[60] <= 8'h3c;
		mem[61] <= 8'h3d;
		mem[62] <= 8'h3e;
		mem[63] <= 8'h3f;
		mem[64] <= 8'h40;
		mem[65] <= 8'h41;
		mem[66] <= 8'h42;
		mem[67] <= 8'h43;
		mem[68] <= 8'h44;
		mem[69] <= 8'h45;
		mem[70] <= 8'h46;
		mem[71] <= 8'h47;
		mem[72] <= 8'h48;
		mem[73] <= 8'h49;
		mem[74] <= 8'h4a;
		mem[75] <= 8'h4b;
		mem[76] <= 8'h4c;
		mem[77] <= 8'h4d;
		mem[78] <= 8'h4e;
		mem[79] <= 8'h4f;
		mem[80] <= 8'h50;
		mem[81] <= 8'h51;
		mem[82] <= 8'h52;
		mem[83] <= 8'h53;
		mem[84] <= 8'h54;
		mem[85] <= 8'h55;
		mem[86] <= 8'h56;
		mem[87] <= 8'h57;
		mem[88] <= 8'h58;
		mem[89] <= 8'h59;
		mem[90] <= 8'h5a;
		mem[91] <= 8'h5b;
		mem[92] <= 8'h5c;
		mem[93] <= 8'h5d;
		mem[94] <= 8'h5e;
		mem[95] <= 8'h5f;
		mem[96] <= 8'h60;
		mem[97] <= 8'h61;
		mem[98] <= 8'h62;
		mem[99] <= 8'h63;
		mem[100] <= 8'h64;
		mem[101] <= 8'h65;
		mem[102] <= 8'h66;
		mem[103] <= 8'h67;
		mem[104] <= 8'h68;
		mem[105] <= 8'h69;
		mem[106] <= 8'h6a;
		mem[107] <= 8'h6b;
		mem[108] <= 8'h6c;
		mem[109] <= 8'h6d;
		mem[110] <= 8'h6e;
		mem[111] <= 8'h6f;
		mem[112] <= 8'h70;
		mem[113] <= 8'h71;
		mem[114] <= 8'h72;
		mem[115] <= 8'h73;
		mem[116] <= 8'h74;
		mem[117] <= 8'h75;
		mem[118] <= 8'h76;
		mem[119] <= 8'h77;
		mem[120] <= 8'h78;
		mem[121] <= 8'h79;
		mem[122] <= 8'h7a;
		mem[123] <= 8'h7b;
		mem[124] <= 8'h7c;
		mem[125] <= 8'h7d;
		mem[126] <= 8'h7e;
		mem[127] <= 8'h7f;
		mem[128] <= 8'h80;
		mem[129] <= 8'h81;
		mem[130] <= 8'h82;
		mem[131] <= 8'h83;
		mem[132] <= 8'h84;
		mem[133] <= 8'h85;
		mem[134] <= 8'h86;
		mem[135] <= 8'h87;
		mem[136] <= 8'h88;
		mem[137] <= 8'h89;
		mem[138] <= 8'h8a;
		mem[139] <= 8'h8b;
		mem[140] <= 8'h8c;
		mem[141] <= 8'h8d;
		mem[142] <= 8'h8e;
		mem[143] <= 8'h8f;
		mem[144] <= 8'h90;
		mem[145] <= 8'h91;
		mem[146] <= 8'h92;
		mem[147] <= 8'h93;
		mem[148] <= 8'h94;
		mem[149] <= 8'h95;
		mem[150] <= 8'h96;
		mem[151] <= 8'h97;
		mem[152] <= 8'h98;
		mem[153] <= 8'h99;
		mem[154] <= 8'h9a;
		mem[155] <= 8'h9b;
		mem[156] <= 8'h9c;
		mem[157] <= 8'h9d;
		mem[158] <= 8'h9e;
		mem[159] <= 8'h9f;
		mem[160] <= 8'ha0;
		mem[161] <= 8'ha1;
		mem[162] <= 8'ha2;
		mem[163] <= 8'ha3;
		mem[164] <= 8'ha4;
		mem[165] <= 8'ha5;
		mem[166] <= 8'ha6;
		mem[167] <= 8'ha7;
		mem[168] <= 8'ha8;
		mem[169] <= 8'ha9;
		mem[170] <= 8'haa;
		mem[171] <= 8'hab;
		mem[172] <= 8'hac;
		mem[173] <= 8'had;
		mem[174] <= 8'hae;
		mem[175] <= 8'haf;
		mem[176] <= 8'hb0;
		mem[177] <= 8'hb1;
		mem[178] <= 8'hb2;
		mem[179] <= 8'hb3;
		mem[180] <= 8'hb4;
		mem[181] <= 8'hb5;
		mem[182] <= 8'hb6;
		mem[183] <= 8'hb7;
		mem[184] <= 8'hb8;
		mem[185] <= 8'hb9;
		mem[186] <= 8'hba;
		mem[187] <= 8'hbb;
		mem[188] <= 8'hbc;
		mem[189] <= 8'hbd;
		mem[190] <= 8'hbe;
		mem[191] <= 8'hbf;
		mem[192] <= 8'hc0;
		mem[193] <= 8'hc1;
		mem[194] <= 8'hc2;
		mem[195] <= 8'hc3;
		mem[196] <= 8'hc4;
		mem[197] <= 8'hc5;
		mem[198] <= 8'hc6;
		mem[199] <= 8'hc7;
		mem[200] <= 8'hc8;
		mem[201] <= 8'hc9;
		mem[202] <= 8'hca;
		mem[203] <= 8'hcb;
		mem[204] <= 8'hcc;
		mem[205] <= 8'hcd;
		mem[206] <= 8'hce;
		mem[207] <= 8'hcf;
		mem[208] <= 8'hd0;
		mem[209] <= 8'hd1;
		mem[210] <= 8'hd2;
		mem[211] <= 8'hd3;
		mem[212] <= 8'hd4;
		mem[213] <= 8'hd5;
		mem[214] <= 8'hd6;
		mem[215] <= 8'hd7;
		mem[216] <= 8'hd8;
		mem[217] <= 8'hd9;
		mem[218] <= 8'hda;
		mem[219] <= 8'hdb;
		mem[220] <= 8'hdc;
		mem[221] <= 8'hdd;
		mem[222] <= 8'hde;
		mem[223] <= 8'hdf;
		mem[224] <= 8'he0;
		mem[225] <= 8'he1;
		mem[226] <= 8'he2;
		mem[227] <= 8'he3;
		mem[228] <= 8'he4;
		mem[229] <= 8'he5;
		mem[230] <= 8'he6;
		mem[231] <= 8'he7;
		mem[232] <= 8'he8;
		mem[233] <= 8'he9;
		mem[234] <= 8'hea;
		mem[235] <= 8'heb;
		mem[236] <= 8'hec;
		mem[237] <= 8'hed;
		mem[238] <= 8'hee;
		mem[239] <= 8'hef;
		mem[240] <= 8'hf0;
		mem[241] <= 8'hf1;
		mem[242] <= 8'hf2;
		mem[243] <= 8'hf3;
		mem[244] <= 8'hf4;
		mem[245] <= 8'hf5;
		mem[246] <= 8'hf6;
		mem[247] <= 8'hf7;
		mem[248] <= 8'hf8;
		mem[249] <= 8'hf9;
		mem[250] <= 8'hfa;
		mem[251] <= 8'hfb;
		mem[252] <= 8'hfc;
		mem[253] <= 8'hfd;
		mem[254] <= 8'hfe;
		mem[255] <= 8'hff;
	end

	wire [7:0] addr_reg;
	always @(posedge clk) begin
		addr_reg <= addr;
	end
	data_out <= mem[addr_reg];

endmodule


