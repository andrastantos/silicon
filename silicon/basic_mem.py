from silicon import *
from typing import List

class BasicMemory(GenericModule):
    class MemoryPort(object):
        def __init__(self):
            self.data_in = Input(default_value=None)
            self.write_en = Input(default_value=0)
            self.addr = Input()
            self.data_out = Output()

    def construct(self, port_cnt: int):
        self.mem_ports: List[BasicMemory.MemoryPort] = []
        for idx in range(port_cnt):
            port = BasicMemory.MemoryPort()
            setattr(self, f"data_in_{idx}_port", port.data_in)
            setattr(self, f"write_en_{idx}_port", port.write_en)
            setattr(self, f"addr_{idx}_port", port.addr)
            setattr(self, f"data_out_{idx}_port", port.data_out)
            self.mem_ports.append(port)

    def set_port_type(self, port_idx: int, net_type: NetType):
        if port_idx > len(self.mem_ports):
            raise SyntaxErrorException(f"BasicMemory {self} doesn't have a port {port_idx}")
        port = self.mem_ports[port_idx]
        if not is_number(net_type):
            raise SyntaxErrorException(f"BasicMemory {self} only support Number-based interface types")
        port.data_out.set_net_type(net_type)
        port.data_in.set_net_type(net_type)

    def body(self):
        self.content_trigger = Wire(logic)

    def _setup(self):
        for idx, port in enumerate(self.mem_ports):
            try:
                try:
                    port.width = port.data_in.get_net_type().get_num_bits()
                    if not is_number(port.data_in.get_net_type()):
                        raise SyntaxErrorException(f"BasicMemory {self} only support Number-based interface types")
                except AttributeError:
                    port.width = port.data_out.get_net_type().get_num_bits()
            except AttributeError:
                raise SyntaxErrorException(f"Memory port {idx} for {self} has neither its data input or output connected")

            try:
                port.depth = port.addr.get_net_type().get_num_bits()
                if not is_number(port.addr.get_net_type()):
                    raise SyntaxErrorException(f"BasicMemory {self} only support Number-based interface types")
            except AttributeError:
                raise SyntaxErrorException(f"Memory port {idx} for {self} has doesn't have its address port connected")
            port.has_read = port.data_out.get_net_type() is not None # Not precise, but good enough: the only reason reads would fail if the output junction has no type

        max_width = max(port.width for port in self.mem_ports)
        for idx, port in enumerate(self.mem_ports):
            if max_width % port.width != 0:
                raise SyntaxErrorException(f"Memory width {max_width} is not divisible by width {port.width} of port {idx} for {self}.")

    def simulate(self, simulator: Simulator) -> TSimEvent:
        # We have some optional ports, but those would have drivers by this stage: a constant 'None' or '0' driver
        # We will simply trigger on all write_en and address ports, plus our own internal content_trigger
        trigger_ports = []
        for port in self.mem_ports:
            trigger_ports.append(port.write_en)
            trigger_ports.append(port.addr)
        trigger_ports.append(self.content_trigger)

        self._setup()

        content = {}
        content_width = min(port.width for port in self.mem_ports)

        def read_mem(addr: int, data_width: int) -> int:
            value = 0
            burst_size = data_width // content_width
            start_addr = addr * burst_size
            data_mask = (1 << data_width) - 1
            for burst_addr in range(start_addr + burst_size - 1, start_addr - 1, -1):
                try:
                    data_section = content[burst_addr]
                except KeyError:
                    return None
                if data_section is None:
                    return None
                value = (value >> data_width) | (data_section & data_mask)
            return value

        def write_mem(addr:int, value: int, data_width: int):
            burst_size = data_width // content_width
            start_addr = addr * burst_size
            data_mask = (1 << data_width) - 1
            burst_value = value
            for burst_addr in range(start_addr, start_addr + burst_size):
                if burst_value is not None:
                    content[burst_addr] = burst_value & data_mask
                    burst_value >>= data_width
                else:
                    content[burst_addr] = None

        while True:
            yield trigger_ports

            now = simulator.now
            print(f"{now:4d} Memory got triggered")
            # This is an asynchronous memory with 'read-old-value' behavior.
            # However, if any writes are performed, that will trigger a 'content_trigger' change
            # So we will come back in the next epsilon step and do another read. This behavior
            # is good enough to capture the output in registers, if needed, but also properly
            # simulates the fact that this is an asynchronous array
            for port in self.mem_ports:
                # Read ports should only care about content and address changes
                if port.addr.get_sim_edge() == EdgeType.NoEdge and self.content_trigger.get_sim_edge() == EdgeType.NoEdge:
                    continue
                if not port.has_read:
                    continue
                try:
                    addr = int(port.addr.sim_value)
                except (TypeError, ValueError):
                    port.data_out <<= None
                    continue
                raw_value = read_mem(addr, port.width)
                print(f"{now:4d} reading {addr} with value {raw_value}")
                port.data_out <<= raw_value

            for port in self.mem_ports:
                we_edge_type = port.write_en.get_sim_edge()
                if we_edge_type == EdgeType.Undefined:
                    # We don't know if there was an edge: clear the whole memory
                    content.clear()
                    continue
                if we_edge_type == EdgeType.Positive:
                    try:
                        addr = int(port.addr.sim_value)
                    except (TypeError, ValueError):
                        # There was an edge, but we don't know which address was written: clear the whole memory
                        content.clear()
                        continue
                    try:
                        raw_value = int(port.data_in.sim_value)
                    except (TypeError, ValueError):
                        raw_value = None

                    print(f"{now:4d} writing {addr} with value {raw_value}")
                    write_mem(addr, raw_value, port.width)

                    self.content_trigger <<= 1 if self.content_trigger == 0 else 0



def test_simple():
    class Top(Module):
        def body(self):
            self.data_in = Wire(Unsigned(8))
            self.data_out = Wire(Unsigned(8))
            self.addr = Wire(Unsigned(7))
            self.write_en = Wire(logic)

            self.reg_data = Reg(self.data_out, clock_port=self.write_en)
            mem = BasicMemory(port_cnt=1)
            mem.set_port_type(0, Unsigned(8))
            mem.data_in_0_port <<= self.data_in
            self.data_out <<= mem.data_out_0_port
            mem.addr_0_port <<= self.addr
            mem.write_en_0_port <<= self.write_en

        def simulate(self, simulator):
            self.write_en <<= 0
            yield 10
            for i in range(10):
                self.data_in <<= i
                self.addr <<= i
                self.write_en <<= 1
                yield 5
                self.write_en <<= 0
                yield 5
                assert self.data_out == i
            for i in range(10):
                self.data_in <<= i+100
                self.addr <<= i
                yield 1
                self.write_en <<= 1
                yield 5
                self.write_en <<= 0
                yield 5
                assert self.data_out == i+100
                assert self.reg_data == i

    Build.simulation(Top, "test_simple.vcd", add_unnamed_scopes=True)

if __name__ == "__main__":
    test_simple()

