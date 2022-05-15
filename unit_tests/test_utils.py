from silicon import SystemVerilog, File, Module, Junction, NetType, Number, Simulator, Module, elaborate, BoolMarker
from silicon.utils import is_iterable, CountMarker, BoolMarker
from typing import IO, Callable, Sequence, Union, Optional, Any
from collections import OrderedDict
from silicon.ordered_set import OrderedSet
import pytest
from pathlib import Path

class test:
    file_list = []

    skip_iverilog = BoolMarker()
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
    def rtl_generation(top_class: Union[Callable, Module], test_name: str = None, allow_new_attributes: bool = False):
        if test_name is None:
            test_name = top_class.__name__.lower()
        import os
        test.clear()
        test.reference_dir = Path("reference") / test_name
        test.output_dir = Path("output") / test_name
        if isinstance(top_class, Module):
            top = top_class
        else:
            top = top_class()
        netlist = elaborate(top)
        logged_system_verilog = SystemVerilog(stream_class = test.DiffedFile)
        netlist.generate(netlist, logged_system_verilog)
        #with test.DiffedFile(f"{test_name}.dmp", "w", allow_added_lines=allow_new_attributes) as dump_file:
        #    Writer(dump_file).dump(netlist)
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
        if not test.skip_iverilog:
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
    def simulation(top_class: Callable, test_name: str = None):
        if test_name is None:
            test_name = top_class.__name__.lower()
        test.clear()
        test.reference_dir = Path("reference") / Path(test_name)
        test.output_dir = Path("output") / Path(test_name)
        top = top_class()
        netlist = elaborate(top)
        test.output_dir.mkdir(parents=True, exist_ok=True)
        vcd_filename = test.output_dir / Path(f"{test_name}.vcd")
        netlist.simulate(vcd_filename)
        print(f"Simulation results saved into {Path(vcd_filename).absolute()}")
        #with test.DiffedFile(f"{test_name}.dmp", "w", allow_added_lines=allow_new_attributes) as dump_file:
        #    Writer(dump_file).dump(netlist)
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

class Writer(object):
    global_dump_exclude = ("__class__", "__dir__", "__dict__", "__doc__", "__module__", "__weakref__", "__annotations__", "__slotnames__", "__isabstractmethod__", "dump_exclude", "dump_no_recurse")
    global_dump_no_recurse = ()
    dump_exclude = {
        Module: ("_in_new_lock", "_parent_module_lock", "_filename", "_class_filename", "_parent_modules"),
    }
    dump_no_recurse = {
        Module: ("_ports", "_inputs", "_positional_inputs", "_outputs", "_positional_outputs", "_sub_modules", "_symbol_table", "netlist"),
        Junction: ("sinks", "source", "parent_module")
    }
    primitive_types = (
        int,
        float,
        str,
        bool,
        BoolMarker,
        Number,
        slice
    )

    def __init__(self, strm: Optional[IO]=None):
        from sys import stdout
        self.strm = strm if strm is not None else stdout
        self.clear()

    def clear(self):
        self.dump_level = CountMarker()
        self.obj_refs = OrderedDict() # Key is an object, the value is an ID string and a flag that's True if the object has already been dumped
        self.obj_counts = OrderedDict() # Key is a type object, value is the number of such objects that have been seen
        self.need_indent = False

    def get_object_ref(self, thing, being_dumped: bool=False) -> str:
        if thing not in self.obj_refs:
            obj_type = type(thing)
            if obj_type not in self.obj_counts:
                self.obj_counts[obj_type] = 0
            self.obj_counts[obj_type] += 1
            ref_name = f"{obj_type.__name__}_{self.obj_counts[obj_type]}"
            self.obj_refs[thing] = {"ref_name":ref_name, "dumped":being_dumped}
        else:
            self.obj_refs[thing]["dumped"]|=being_dumped
        return self.obj_refs[thing]["ref_name"]

    def _dump(self, thing, name: Optional[str] = None, no_rescurse: bool = False) -> None:
        def write(message: str) -> None:
            indent = "    " * int(self.dump_level)
            if self.need_indent:
                message = indent + message
                self.need_indent = False
            if message[-1] == "\n":
                message = message[:-1]
                self.need_indent = True
            message = message.replace("\n", "\n"+indent)
            if self.need_indent:
                message += "\n"
            self.strm.write(message)
            self.strm.flush()

        def get_key_str(thing: Any) -> str:
            if type(thing) in self.primitive_types:
                return str(thing)
            elif thing is None:
                return "None"
            else:
                return f"@{self.get_object_ref(thing, False)}"

        if int(self.dump_level) > 10:
            print("boo!")

        class_name = type(thing).__name__

        if name is not None:
            write(f"{name}: ")

        if isinstance(thing, self.primitive_types):
            write(f"{class_name} = ")
            write(f"{repr(thing)}\n")
        elif isinstance(thing, dict):
            write(f"{class_name} = ")
            if len(thing) > 0:
                with self.dump_level:
                    write("{\n")
                    for key, value in thing.items():
                        self._dump(value, get_key_str(key), no_rescurse)
                write("}\n")
            else:
                write("{}\n")
        elif isinstance(thing, (list, tuple)):
            write(f"{class_name} = ")
            if len(thing) > 0:
                with self.dump_level:
                    write("(\n")
                    for idx, value in enumerate(thing):
                        self._dump(value, f"#{idx}", no_rescurse)
                write(")\n")
            else:
                write("()\n")
        elif isinstance(thing, (set, OrderedSet)):
            write(f"{class_name} = ")
            if len(thing) > 0:
                with self.dump_level:
                    write("(\n")
                    for value in thing:
                        self._dump(value, None, no_rescurse)
                write(")\n")
            else:
                write("()\n")
        elif thing is None:
            write(f"NoneType = None\n")
        elif isinstance(thing, type):
            write(f"type = {thing.__name__}\n")
        elif isinstance(thing, object):
            dump_exclude = list(self.global_dump_exclude)
            for class_category, exclude_list in self.dump_exclude.items():
                if isinstance(thing, class_category):
                    dump_exclude += list(exclude_list)
            if hasattr(thing, "dump_exclude"):
                dump_exclude += list(thing.dump_eclude)

            dump_no_recurse = list(self.global_dump_no_recurse)
            for class_category, no_recurse_list in self.dump_no_recurse.items():
                if isinstance(thing, class_category):
                    dump_no_recurse += list(no_recurse_list)
            if hasattr(thing, "dump_no_recurse"):
                dump_no_recurse += list(thing.dump_no_recurse)

            thing_ref = self.get_object_ref(thing, True)
            if no_rescurse:
                # We won't recurse into the object itself, just note a reference to it.
                write(f"{class_name} = @{self.get_object_ref(thing, False)}\n")
            else:
                with self.dump_level:
                    write(f"{class_name} @{thing_ref} = [\n")
                    for attr_name in dir(thing):
                        try:
                            attr_val = getattr(thing, attr_name)
                        except Exception as ex:
                            attr_val = f"<<<exception: {type(ex).__name__}({str(ex)})>>>"
                        if callable(attr_val):
                            continue
                        if attr_name in dump_exclude:
                            continue
                        self._dump(attr_val, attr_name, (attr_name in dump_no_recurse) | no_rescurse)
                write("]\n")
        else:
            write(f"{str(thing)}\n")

        if self.dump_level == 0:
            # We're at the end of the top level: look for referenced, but not dumped objects and dump them
            first = True
            for obj, desc in self.obj_refs:
                if not desc["dumped"]:
                    if first:
                        with self.dump_level:
                            write("<<orphans>> = (\n")
                        first = False
                    with self.dump_level:
                        self.dump(obj, f"[{desc['ref_name']}]")
            if not first:
                write(")\n")

    def dump(self, thing, name: Optional[str] = None) -> None:
        self.clear()
        self._dump(thing, name)

# A simple decorator to skip iVerilog on tests that are known to fail on it due to iVerilog limitations
def skip_iverilog(func):
    def wrapper(*args, **kwargs):
        with test.skip_iverilog:
            return func(*args, **kwargs)

    return wrapper

