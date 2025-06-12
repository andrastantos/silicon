import silicon as si

class Alu(si.Module):
    in_a = si.Input()
    in_b = si.Input()
    in_c = si.Input(si.logic)
    out_r = si.Output()
    out_c = si.Output()

    operation = si.Input()

    def body(self):
        full_add = si.Wire(si.Unsigned(max(self.in_a.get_num_bits(), self.in_b.get_num_bits())+1))

        full_add <<= self.in_a + self.in_b + self.in_c
        self.out_r <<= si.Select(
            self.operation,
            #full_add[full_add.get_num_bits()-2:0],
            full_add["boo":0],
            self.in_a & self.in_b,
            self.in_a | self.in_b,
            self.in_a ^ self.in_b
        )
        self.out_c <<= full_add[full_add.get_num_bits()-1]


class Alu32(si.Module):
    in_a = si.Input(si.Unsigned(32))
    in_b = si.Input(si.Unsigned(32))
    in_c = si.Input(si.logic)
    out_r = si.Output(si.Unsigned(32))
    out_c = si.Output(si.logic)

    operation = si.Input(si.Unsigned(2))

    def body(self):
        (o_r, o_c) = Alu(self.in_a, self.in_b, self.in_c, self.operation)
        self.out_r <<= o_r
        self.out_c <<= o_c

with si.Netlist().elaborate() as netlist:
    Alu32()
rtl = si.StrStream()
netlist.generate(si.SystemVerilog(rtl))
print(rtl)
