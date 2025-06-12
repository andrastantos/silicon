import silicon as si

class FullAdder(si.Module):
    in_a = si.Input(si.logic)
    in_b = si.Input(si.logic)
    in_c = si.Input(si.logic)
    out_r = si.Output(si.logic)
    out_c = si.Output(si.logic)

    def body(self):
        xor2_result = si.Wire()

        xor1 = si.xor_gate()
        xor2 = si.xor_gate()
        and1 = si.and_gate()
        and2 = si.and_gate()
        and3 = si.and_gate()
        or1 = si.or_gate()

        xor1.input_port_0 <<= self.in_a
        xor1.input_port_1 <<= self.in_b
        xor2.input_port_0 <<= xor1.output_port
        xor2.input_port_1 <<= self.in_c
        xor2_result <<= xor2.output_port
        self.out_r <<= xor2_result

        and1.input_port_0 <<= self.in_a
        and1.input_port_1 <<= self.in_b
        and2.input_port_0 <<= self.in_b
        and2.input_port_1 <<= self.in_c
        and3.input_port_0 <<= self.in_c
        and3.input_port_1 <<= self.in_a
        or1.input_port_0 <<= and1.output_port
        or1.input_port_1 <<= and2.output_port
        or1.input_port_2 <<= and3.output_port

        self.out_c <<= or1.output_port

with si.Netlist().elaborate() as netlist:
    FullAdder()
rtl = si.StrStream()
netlist.generate(si.SystemVerilog(rtl))
print(rtl)
