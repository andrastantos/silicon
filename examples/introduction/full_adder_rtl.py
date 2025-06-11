import silicon as si

class FullAdder(si.Module):
    in_a = si.Input(si.logic)
    in_b = si.Input(si.logic)
    in_c = si.Input(si.logic)
    out_r = si.Output(si.logic)
    out_c = si.Output(si.logic)

    def body(self):
        self.out_r <<= self.in_a ^ self.in_b ^ self.in_c
        self.out_c <<= (self.in_a & self.in_b) | (self.in_b & self.in_c) | (self.in_c & self.in_a)

with si.Netlist().elaborate() as netlist:
    FullAdder()
rtl = si.StrStream()
netlist.generate(si.SystemVerilog(rtl))
print(rtl)
