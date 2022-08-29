from silicon import SystemVerilog, File, Build, Netlist
from typing import IO, Callable, Any
import pytest
from pathlib import Path

class test(Build):
    file_list = []

    class DiffedFile(File):
        """
        A trivial file object with delayed open capability
        """
        def __init__(self, filename: str, mode: str, allow_added_lines: bool = False, allow_missing_reference: bool = True):
            super().__init__(filename, mode)
            self.allow_added_lines = allow_added_lines
            self.allow_missing_reference = allow_missing_reference
            self.match = None
            self.diff = None
        def __enter__(self) -> IO:
            self.diff = None
            test.file_list.append(self)
            self.pure_filename = self.filename
            folder = Path(self.pure_filename).parent
            name = Path(self.pure_filename).name
            output_path = test.output_dir / folder
            reference_path = folder / test.reference_dir
            self.filename = output_path / name
            self.reference_filename = reference_path / name
            output_path.mkdir(parents=True, exist_ok=True)
            return super().__enter__()
        def __exit__(self, exception_type, exception_value, traceback):
            stream = self.stream
            self.stream = None
            ret_val = stream.__exit__(exception_type, exception_value, traceback)
            if exception_value is not None:
                # There was an exception: record that as the difference and don't bother with the file
                self.diff = str(exception_value)
            else:
                # We have been successful in generating the file, let's compare!
                import difflib
                if self.reference_filename.exists():
                    with self.reference_filename.open("r") as reference_file:
                        reference_content = reference_file.readlines()
                    with self.filename.open("r") as test_file:
                        test_content = test_file.readlines()
                    diff = difflib.unified_diff(reference_content, test_content, str(self.reference_filename), str(self.filename), n = 3)
                    self.match = True
                    for diff_line in diff:
                        if self.diff is None:
                            self.diff = ""
                        self.diff += diff_line
                        if not diff_line.startswith("---") and (diff_line[0] == "-" or not self.allow_added_lines):
                            self.match = False
                else:
                    import warnings
                    self.diff = f"No reference file '{self.reference_filename.absolute()}' found for output file '{self.filename.absolute()}'"
                    if self.allow_missing_reference:
                        warnings.warn(UserWarning(self.diff))
                        self.match = True
                    else:
                        self.match = False
            return ret_val

    @staticmethod
    def rtl_generation(top_class: Callable, test_name: str = None, allow_new_attributes: bool = False, *, add_unnamed_scopes: bool = False):
        if test_name is None:
            test_name = top_class.__name__.lower()
        import os
        test.clear()
        test.reference_dir = Path("reference") / test_name
        test.output_dir = Path("output") / test_name
        netlist = Netlist()
        with netlist.elaborate(add_unnamed_scopes=add_unnamed_scopes):
            top_class()
        logged_system_verilog = SystemVerilog(stream_class = test.DiffedFile)
        netlist.generate(logged_system_verilog)
        test_diff = ""
        success = True
        for file in test.file_list:
            if file.diff is not None:
                test_diff += "\n\n"+"-"*80+"\n"
                test_diff += file.diff
            success &= file.match
        if not success:
            if test_diff == "":
                for file in test.file_list:
                    test_diff += f"file {file.filename} match: {file.match}"
            pytest.fail(f"Test failed with the following diff:\n{test_diff}")
        if not Build._skip_iverilog:
            from shutil import which
            iverilog_path = which("iverilog", mode=os.X_OK)
            if iverilog_path is not None:
                from subprocess import run
                top = netlist.get_top_level_name()
                cmd = (iverilog_path, "-g2005-sv", f"-s{top}") + tuple(f.filename for f in test.file_list)
                result = run(cmd)
                if result.returncode != 0:
                    pytest.fail(f"Test failed with IVerilog errors")

    @staticmethod
    def simulation(top_class: Callable, test_name: str = None, *, add_unnamed_scopes: bool = False):
        if test_name is None:
            test_name = top_class.__name__.lower()
        test.clear()
        test.reference_dir = Path("reference") / Path(test_name)
        test.output_dir = Path("output") / Path(test_name)
        netlist = Netlist()
        with netlist.elaborate(add_unnamed_scopes=add_unnamed_scopes):
            top_class()
        test.output_dir.mkdir(parents=True, exist_ok=True)
        vcd_filename = test.output_dir / Path(f"{test_name}.vcd")
        netlist.simulate(vcd_filename)
        print(f"Simulation results saved into {Path(vcd_filename).absolute()}")
        test_diff = ""
        success = True
        for file in test.file_list:
            if file.diff is not None:
                test_diff += "\n\n"+"-"*80+"\n"
                test_diff += file.diff
            success &= file.match
        if not success:
            if test_diff == "":
                for file in test.file_list:
                    test_diff += f"file {file.filename} match: {file.match}"
            pytest.fail(f"Test failed with the following diff:\n{test_diff}")

    @staticmethod
    def clear():
        test.file_list.clear()

class ExpectError(object):
    def __init__(self, *args):
        if len(args) == 0:
            self.filter = None
        else:
            self.filter = args
    def __enter__(self) -> 'ExpectError':
        return self
    def __exit__(self, exception_type, exception_value, traceback):
        if self.filter is None:
            # If no filter is given, ignore any exception, but make sure there was one
            if exception_type is None:
                assert False, "Exception expected, but none occurred"
            return True
        else:
            # We have a list of exception types: make sure the exception is in it:
            if exception_type is None:
                assert False, "Exception expected, but none occurred"
            # Silence all filtered exceptions, re-raise all others
            return exception_type in self.filter

