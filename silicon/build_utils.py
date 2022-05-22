from .exceptions import IVerilogException
from .back_end import SystemVerilog, File
from .module import Module, elaborate
from .utils import BoolMarker
from typing import Callable, Union

class Build:
    __file_list = []

    __skip_iverilog = BoolMarker()

    @staticmethod
    def generate_rtl(top_class: Union[Callable, Module], *, add_unnamed_scopes: bool = False):
        Build.clear()
        if isinstance(top_class, Module):
            top = top_class
        else:
            top = top_class()
        netlist = elaborate(top, add_unnamed_scopes=add_unnamed_scopes)
        system_verilog = SystemVerilog(stream_class = File)
        netlist.generate(netlist, system_verilog)
        if not Build.__skip_iverilog:
            from shutil import which
            iverilog_path = which("iverilog", mode=os.X_OK)
            if iverilog_path is not None:
                from subprocess import run
                top = netlist.get_top_level_name()
                cmd = (iverilog_path, "-g2005-sv", f"-s{top}") + tuple(f.filename for f in test.__file_list)
                result = run(cmd)
                if result.returncode != 0:
                    raise IVerilogException(f"IVerilog failed with error code {result.returncode}")

    @staticmethod
    def simulation(top_class: Callable, vcd_filename: str = None, *, add_unnamed_scopes: bool = False):
        if vcd_filename is None:
            vcd_filename = top_class.__name__.lower()
        Build.clear()
        top = top_class()
        netlist = elaborate(top, add_unnamed_scopes=add_unnamed_scopes)
        netlist.simulate(vcd_filename)

    @staticmethod
    def clear():
        Build.__file_list.clear()


# A simple decorator to skip iVerilog on tests that are known to fail on it due to iVerilog limitations
def skip_iverilog(func):
    def wrapper(*args, **kwargs):
        with Build.__skip_iverilog:
            return func(*args, **kwargs)

    return wrapper

