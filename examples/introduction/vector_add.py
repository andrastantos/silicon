import silicon as si

class VectorAdder(si.Module):
    in_a = si.Input(si.Unsigned(8))
    in_b = si.Input(si.Unsigned(8))
    in_c = si.Input(si.logic)
    out_r = si.Output(si.Unsigned(8))
    out_c = si.Output(si.logic)

    def body(self):
        full_result = si.Wire(si.Unsigned(9))

        full_result <<= self.in_a + self.in_b + self.in_c
        self.out_r <<= full_result[7:0]
        self.out_c <<= full_result[8]

with si.Netlist().elaborate() as netlist:
    VectorAdder()
rtl = si.StrStream()
netlist.generate(si.SystemVerilog(rtl))
print(rtl)
