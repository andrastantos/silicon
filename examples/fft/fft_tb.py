import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".." / ".."))
sys.path.append(str(Path(__file__).parent / ".." / ".." / "unit_tests"))

from typing import *

from silicon import *
from test_utils import *


from fft import *


def test_butterfly_mem_verilog():
    test.rtl_generation(ButterflyMem(addr_len=8,level=4), "butterfly_mem")

def test_butterfly_mem_sim():

    frame_size = 16
    class TB(Module):
        def body(self):
            uut = ButterflyMem(addr_len=frame_size.bit_length(), level=1)

            self.clk = Wire(logic)
            self.rst = Wire(logic)

            self.input_data = Wire(ComplexStream())
            self.output_data = Wire(ComplexStream())
            self.flush_in = Wire(trigger)
            self.flush_out = Wire(trigger)

            uut.clk <<= self.clk
            uut.rst <<= self.rst
            uut.input_data <<= self.input_data
            self.output_data <<= uut.output_data
            uut.flush_in <<= self.flush_in
            self.flush_out <<= uut.flush_out

        def simulate(self) -> TSimEvent:
            # NOTE: we're going to use rdXX register addresses for both reads and writes
            def clk() -> int:
                yield 10
                self.clk <<= ~self.clk
                yield 10
                self.clk <<= ~self.clk
                yield 0

            def send_data(data):
                self.input_data.data <<= data
                self.input_data.valid <<= 1
                yield from clk()
                while (not self.input_data.ready):
                    yield from clk()
                self.input_data.valid <<= 0

            def send_rcv_data(data, expected, timeout = None):
                self.input_data.data <<= data
                self.input_data.valid <<= 1
                self.output_data.ready <<= 1
                yield from clk()
                cnt = 0
                while (not self.input_data.ready or not self.output_data.valid):
                    yield from clk()
                    cnt += 1
                    if timeout is not None and cnt == timeout:
                        assert False, "Timeout waiting for memory"
                assert self.output_data.data == expected, f"output data {self.output_data.data} doesn't match expected value {expected}"
                self.input_data.valid <<= 0
                self.output_data.ready <<= 0

            def do_reset():
                self.rst <<= 1
                self.clk <<= 1
                self.flush_in <<= 0
                yield 10
                for i in range(5):
                    yield from clk()
                self.input_data.valid <<= 0
                self.output_data.ready <<= 0
                for i in range(5):
                    yield from clk()
                self.rst <<= 0

            def send_input(real: int = 0, img: int = 0, last: bool=False, wait: bool=False):
                self.input_data.data <<= ComplexType()(real, img)
                self.input_data.last <<= last
                self.input_data.valid <<= 1
                if wait:
                    while True:
                        yield from clk()
                        if self.input_data.ready: break
                    self.input_data.valid <<= 0
                    self.input_data.data <<= None
                    self.input_data.last <<= None

            def test_output(real: int = 0, img: int = 0, last: bool=False, wait: bool=False):
                pass

            def send_frame():
                for i in range(frame_size-1):
                    yield from send_input(i, 0, last=False, wait=True)
                yield from send_input(i,0, last=True, wait=True)

            print("Simulation started")
            yield from do_reset()
            print("Init complete")
            self.output_data.ready <<= 1
            for _ in range(5):
                yield from clk()
            for i in range(4):
                yield from send_frame()
                for i2 in range(5):
                    yield from clk()
            print(f"Done")

    test.simulation(TB, "fft_mem_tb")

if __name__ == "__main__":
    test_butterfly_mem_sim()
    #test_butterfly_mem_verilog()
