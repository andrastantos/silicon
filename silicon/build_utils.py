from .exceptions import IVerilogException
from .back_end import SystemVerilog, File
from .netlist import Netlist
from .utils import ScopedAttr
from typing import Callable, IO, Optional, Union, Dict
import os

class Build:
    _file_list = []

    _skip_iverilog = False

    class RegisteredFile(File):
        """
        Register the file in a global list
        """
        def __enter__(self) -> IO:
            Build._file_list.append(self)
            return super().__enter__()

    @staticmethod
    def generate_rtl(top_class: Callable, file_names: Optional[Union[str, Dict[type, str]]] = None):
        Build.clear()
        with Netlist().elaborate() as netlist:
            top = top_class()
        system_verilog = SystemVerilog(stream_class = Build.RegisteredFile)
        netlist.generate(system_verilog, file_names)
        if not Build._skip_iverilog:
            from shutil import which
            iverilog_path = which("iverilog", mode=os.X_OK)
            if iverilog_path is not None:
                from subprocess import run
                top = netlist.get_top_level_name()
                cmd = (iverilog_path, "-g2005-sv", f"-s{top}") + tuple(f.filename for f in Build._file_list)
                result = run(cmd)
                if result.returncode != 0:
                    raise IVerilogException(f"IVerilog failed with error code {result.returncode}")

    @staticmethod
    def simulation(top_class: Callable, vcd_filename: str = None, *, add_unnamed_scopes: bool = False):
        if vcd_filename is None:
            vcd_filename = top_class.__name__.lower()
        Build.clear()
        with Netlist().elaborate() as netlist:
            top = top_class()
        netlist.simulate(vcd_filename, add_unnamed_scopes=add_unnamed_scopes)

    @staticmethod
    def clear():
        Build._file_list.clear()


# A simple decorator to skip iVerilog on tests that are known to fail on it due to iVerilog limitations
def skip_iverilog(func):
    def wrapper(*args, **kwargs):
        with ScopedAttr(Build, "_skip_iverilog", True):
            return func(*args, **kwargs)

    return wrapper

