# Maybe what we want is this: https://docs.python.org/3/library/warnings.html?
from typing import Optional

class SyntaxErrorException(Exception):
    def __init__(self, message, context = None):
        from .utils import is_module
        if is_module(context):
            context = context._impl
        if context is None:
            from .netlist import Netlist
            try:
                context = Netlist.get_current_scope()._impl
            except Exception:
                pass
        loc = None
        try:
            loc = context.get_diagnostic_name(add_location=True)
        except Exception:
            loc = "<<NO LOCATION>>"
        from textwrap import indent, wrap
        if message is not None:
            message = "\n".join(indent("\n".join(wrap(line, width=70)), "    ") for line in message.split("\n"))
            super().__init__(f"{loc}\n{message}")
        else:
            super().__init__(str(loc))

class FixmeException(SyntaxErrorException):
    def __init__(self, message, context = None):
        super().__init__(f"FIXME: {message}", context)

class SimulationException(Exception):
    def __init__(self, message = None, context: Optional['Module'] = None):
        loc = None
        try:
            loc = context.get_diagnostic_name(add_location=True)
        except Exception:
            loc = "<<NO LOCATION>>"
        from textwrap import indent, wrap
        if message is not None:
            message = indent("\n".join(wrap(message, width=70)), "    ")
            super().__init__(f"{loc}\n{message}")
        else:
            super().__init__(str(loc))

class IVerilogException(Exception):
    pass

class AdaptTypeError(Exception):
    pass

class InvalidPortError(Exception):
    pass