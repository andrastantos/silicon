# Maybe what we want is this: https://docs.python.org/3/library/warnings.html?

class SyntaxErrorException(Exception):
    def __init__(self, message, context = None):
        if context is None:
            from .module import Module
            try:
                context = Module.Context.top().context
            except Exception:
                pass
        loc = None
        try:
            loc = context.get_diagnostic_name(add_location=True)
        except Exception:
            loc = "<<NO LOCATION>>"
        from textwrap import indent, wrap
        message = "\n".join(indent("\n".join(wrap(line, width=70)), "    ") for line in message.split("\n"))
        super().__init__(f"{loc}\n{message}")

class SimulationException(Exception):
    def __init__(self, message, context):
        loc = None
        try:
            loc = context.get_diagnostic_name(add_location=True)
        except Exception:
            loc = "<<NO LOCATION>>"
        from textwrap import indent, wrap
        message = indent("\n".join(wrap(message, width=70)), "    ")
        super().__init__(f"{loc}\n{message}")

class IVerilogException(Exception):
    pass
