from .composite import Interface, Reverse
from .number import logic

class ReadyValid(Interface):
    ready = Reverse(logic)
    valid = logic

