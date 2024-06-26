from typing import List, Dict, Any, IO, Tuple, Optional, Sequence, Union
from .module import Module
from collections import OrderedDict
from textwrap import indent
from pathlib import Path
from abc import abstractmethod

class BackEnd(object):
    def __init__(self):
        self.language = ""
    def generate_order(self, netlist: 'Netlist', file_names: Optional[Union[str, Dict[type, str]]] = None) -> Dict[Any, Tuple[Sequence['Module'], Sequence['NetType']]]:
        """
        Returns a list of modules and types per output file name. Modules are going to be generated into their corresponding files in order
        """
        raise NotImplementedError()
    def generate_module(self, module: 'Module') -> str:
        """
        Creates default module body for given module. Only called if module doesn't offer up a specialized implementation.
        """
        raise NotImplementedError()

    @abstractmethod
    def indent(self, lines: str) -> str:
        pass

    @abstractmethod
    def indent_block(self, level: int = 1):
        pass

class File(object):
    """
    A trivial file object with delayed open capability
    """
    def __init__(self, filename: str, mode: str):
        self.filename = filename
        self.mode = mode
        self.stream = None
    def __enter__(self) -> IO:
        if "w" in self.mode or "a" in self.mode:
            # Create path to the filename
            Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
        self.stream = open(self.filename, self.mode)
        return self.stream
    def __exit__(self, exception_type, exception_value, traceback):
        stream = self.stream
        self.stream = None
        return stream.__exit__(exception_type, exception_value, traceback)

class StrStream(object):
    """
    A trivial 'file' object that dumps into a string instead of a file
    """
    def __init__(self):
        from io import StringIO
        self.stream = StringIO()
    def __call__(self, filename: str, mode: str):
        return self
    def __enter__(self) -> IO:
        return self.stream
    def __exit__(self, exception_type, exception_value, traceback):
        pass
    def __str__(self) -> str:
        return self.stream.getvalue()

class SystemVerilog(BackEnd):
    def __init__(self, stream_class = File):
        self.language = "SystemVerilog"
        self.stream_class = stream_class
        self.support_enum = False
        self.support_always_comb = False
        self.support_always_ff = True
        self.support_unique_case = True
        self.support_cast = True
        self.yosys_fix = False
        self.indent_level = 0

    def _generate_file_name_for_module(self, module: 'Module', file_names: Optional[Union[Union[str, Path], Dict[type, Union[str, Path]]]] = None, out_dir: Optional[Union[str, Path]] = None) -> str:
        if file_names is not None:
            if isinstance(file_names, str) or isinstance(file_names, Path):
                return str(file_names)
            try:
                return str(file_names[type(module)])
            except AttributeError:
                pass
        import os
        class_filename = module._impl.get_class_filename()
        class_filename = os.path.splitext(class_filename)[0] + ".sv" if class_filename is not None else "anonymous.sv"
        if out_dir is None:
            return class_filename
        return str(Path(out_dir) / class_filename)

    def get_unconnected_value(self) -> str:
        return f"'X"

    def generate_order(self, netlist: 'Netlist', file_names: Optional[Union[Union[str, Path], Dict[type, Union[str, Path]]]] = None, out_dir: Optional[Union[str, Path]] = None) -> Dict[Any, Tuple[Sequence['Module'], Sequence['NetType']]]:
        """
        Returns a list of modules and types per output file name. Modules are going to be generated into their corresponding files in order

        A stream can be any object, that support the following construct:

        with stream as strm:
            strm.write("xxxx")
            strm.flush()

        That is more or less any IO stream, except that __enter__ should be the one acquiring the resource, not 'open'
        """

        # For now, we simply dump everything into the top-level file
        top_file_name = self._generate_file_name_for_module(netlist.top_level, file_names, out_dir)
        top_file = self.stream_class(top_file_name, "w")
        ret_val = OrderedDict()
        ret_val[top_file] = ([], [])
        for variant in netlist.module_variants.values():
            for variant_instances in variant.values():
                variant_instance = variant_instances[0]
                ret_val[top_file][0].append(variant_instance)
        for _, type_instances in netlist.net_types.items():
            ret_val[top_file][1].append(type_instances[0])
        return ret_val

    UNARY = True
    BINARY = False

    def signed_cast(self, expression: str) -> str:
        return f"$signed({expression})"
    def unsigned_cast(self, expression: str) -> str:
        return f"$unsigned({expression})"

    def get_member_delimiter(self) -> str:
        return "_"

    def get_operator_precedence(self, operator: str, is_unary: bool = None) -> int:
        """
        SystemVerilog operators and their precedence:

        (from IEEE Std 1800-2012 (SystemVerilog Spec 2012), table 11-2)
        """
        operators = (
            # operator                                                                Assoc.  Precedence (highest first, lowest last)
            #########################################################################################################################
            (("()", "[]", "::", "."),                                                 None,   1),
            (("+", "-", "!", "~", "&", "~&", "|", "~|", "^", "~^", "^~", "++", "--"), True,   2),
            (("**",),                                                                 None,   3),
            (("*", "/", "%"),                                                         False,  4),
            (("+", "-"),                                                              False,  5),
            (("<<", ">>", "<<<", ">>>"),                                              None,   6),
            (("<", "<=", ">", ">=", "inside", "dist"),                                None,   7),
            (("==", "!=", "===", "!==", "==?", "!=?"),                                None,   8 if not self.yosys_fix else 15),
            (("&",),                                                                  False,  9),
            (("^", "~^", "^~"),                                                       False, 10),
            (("|",),                                                                  False, 11),
            (("&&",),                                                                 None,  12),
            (("||",),                                                                 None,  13),
            (("?:",),                                                                 None,  14),
            (("->", "<->"),                                                           None,  16),
            (("=", "+=", "-=", "*=", "/=", "%=", "&=", "^=", "|=",
              "<<=", ">>=", "<<<=", ">>>=", ":=", ":/", "<="),                        None,  17),
            (("{}", "{{}}"),                                                          None,  18)
        )
        for ops, unary, precedence in operators:
            if operator in ops and (unary is None or unary == is_unary):
                return precedence
        assert False, f"Unknown operator: {operator}"

    def wrap_expression(self, expression: str, expression_precedence: int, outer_op_precedence: Optional[int]) -> Tuple[str, int]:
        """
        Wraps the expression in parenthesis if needed, based on precedence
        """
        if outer_op_precedence is not None and expression_precedence > outer_op_precedence:
            expression = "(" + expression + ")"
            expression_precedence = self.get_operator_precedence("()")
        return expression, expression_precedence

    def indent(self, lines: str) -> str:
        return indent(lines, "\t" * self.indent_level)

    def indent_block(self, level: int = 1):
        class IndentBlock(object):
            def __init__(self, parent, level):
                self.parent = parent
                self.level = int(level)

            def __enter__(self):
                self.parent.indent_level += self.level
            def __exit__(self, exception_type, exception_value, traceback):
                assert self.parent.indent_level >= self.level
                self.parent.indent_level -= self.level

        return IndentBlock(self, level)

    @staticmethod
    def get_reserved_names() -> Sequence[str]:
        return (
            "reg",
            "accept_on",
            "export",
            "ref",
            "alias",
            "extends",
            "restrict",
            "always_comb",
            "extern",
            "return",
            "always_ff",
            "always",
            "final",
            "s_always",
            "always_latch",
            "first_match",
            "s_eventually",
            "assert",
            "foreach",
            "s_nexttime",
            "assume",
            "forkjoin",
            "s_until",
            "before",
            "global",
            "s_until_with",
            "bind",
            "iff",
            "sequence",
            "bins",
            "ignore_bins",
            "shortint",
            "binsof",
            "illegal_bins",
            "shortreal",
            "bit",
            "implies",
            "solve",
            "break",
            "import",
            "static",
            "byte",
            "inside",
            "string",
            "chandle",
            "int",
            "strong",
            "checker",
            "interface",
            "struct",
            "class",
            "intersect",
            "super",
            "clocking",
            "join_any",
            "sync_accept_on",
            "const",
            "join_none",
            "sync_reject_on",
            "constraint",
            "let",
            "tagged",
            "context",
            "local",
            "this",
            "continue",
            "logic",
            "throughout",
            "cover",
            "longint",
            "timeprecision",
            "covergroup",
            "matches",
            "timeunit",
            "coverpoint",
            "modport",
            "type",
            "cross",
            "new",
            "typedef",
            "dist",
            "nexttime",
            "union",
            "do",
            "null",
            "unique",
            "endchecker",
            "package",
            "unique0",
            "endclass",
            "packed",
            "until",
            "endclocking",
            "priority",
            "until_with",
            "endgroup",
            "program",
            "untypted",
            "endinterface",
            "property",
            "var",
            "endpackage",
            "protected",
            "virtual",
            "endprogram",
            "pure",
            "void",
            "endproperty",
            "rand",
            "wait_order",
            "endsequence",
            "randc",
            "weak",
            "enum",
            "randcase",
            "wildcard",
            "eventually",
            "randsequence",
            "with",
            "expect",
            "reject_on",
            "within"
            "input", # Apparently, even though it's not reserved, most compilers don't like it anways
            "output", # Apparently, even though it's not reserved, most compilers don't like it anways
            "default",
        )

class VHDL(BackEnd):
    @staticmethod
    def get_reserved_names() -> Sequence[str]:
        return (
            "abs",
            "access",
            "after",
            "alias",
            "all",
            "and",
            "architecture",
            "array",
            "assert",
            "attribute",
            "begin",
            "block",
            "body",
            "buffer",
            "bus",
            "case",
            "component",
            "configuration",
            "constant",
            "disconnect",
            "downto",
            "else",
            "elsif",
            "end",
            "entity",
            "exit",
            "file",
            "for",
            "function",
            "generate",
            "generic",
            "group",
            "guarded",
            "if",
            "impure",
            "in",
            "inertial",
            "inout",
            "is",
            "label",
            "library",
            "linkage",
            "literal",
            "loop",
            "map",
            "mod",
            "nand",
            "new",
            "next",
            "nor",
            "not",
            "null",
            "of",
            "on",
            "open",
            "or",
            "others",
            "out",
            "package",
            "port",
            "postponed",
            "procedure",
            "process",
            "pure",
            "range",
            "record",
            "register",
            "reject",
            "return",
            "rol",
            "ror",
            "select",
            "severity",
            "signal",
            "shared",
            "sla",
            "sli",
            "sra",
            "srl",
            "subtype",
            "then",
            "to",
            "transport",
            "type",
            "unaffected",
            "units",
            "until",
            "use",
            "variable",
            "wait",
            "when",
            "while",
            "with",
            "xnor",
            "xor",
        )

system_verilog = SystemVerilog()

def get_reserved_names() -> Sequence[str]:
    return SystemVerilog.get_reserved_names() + VHDL.get_reserved_names()

def str_to_id(name: Any) -> str:
    """
    Transforms name into something that's a safe identifier in all back-ends.
    """
    name = str(name)
    if name in get_reserved_names():
        return "_"+name
    return name.lower().replace(".", "_")