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

class FullAdder_tb(FullAdder):
    def simulate(self):
        for i in range(8):
            expected_sum = (i & 1) + (i >> 1 & 1) + (i >> 2 & 1)
            print(f"Testing case {i} with expected sum {expected_sum}")
            self.in_a <<= (i & 1) != 0
            self.in_b <<= (i & 2) != 0
            self.in_c <<= (i & 4) != 0
            yield 10
            print(f"\tReturned self.out_r:{self.out_r.sim_value} self.out_c:{self.out_c.sim_value}")
            assert self.out_r == expected_sum & 1
            assert self.out_c == expected_sum >> 1 & 1
        print("Pass")


with si.Netlist().elaborate() as netlist:
    FullAdder_tb()
vcd_filename = "full_adder.vcd"
netlist.simulate(vcd_filename)

# You can do it even simpler by using this built-in utility function:
# si.Build.simulation(FullAdder_tb, "full_adder.vcd")
