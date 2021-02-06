from .composite import Interface, Reverse, Struct
from .number import logic
from collections import OrderedDict
from typing import Dict, Tuple, Union
from .net_type import behavior, NetType
from .port import Junction, Input, Output, Wire
from .utils import get_composite_member_name
from .module import Module
from .exceptions import SyntaxErrorException

class ReadyValid(Interface):
    ready = Reverse(logic)
    valid = logic

    def __init__(self):
        super().__init__()
        self._data_member_type = None

    @behavior
    def get_data_members(self) -> Junction:
        output_type = self.get_net_type().get_data_member_type()
        ret_val = Wire(output_type)
        for name, (junction, _) in self.get_member_junctions().items():
            if name not in ("ready", "valid"):
                output_wire = getattr(ret_val, name)
                output_wire <<= junction
        return ret_val

    @behavior
    def set_data_members(self, data_members: Junction):
        # This doesn't usually work: the caching of get_data_member_type() is per instance, so the comparison almost always fails.
        # TODO: how to make the test easier? The code below will blow up if names are not right, but still
        #if data_members.get_net_type() is not self.get_net_type().get_data_member_type():
        #    raise SyntaxErrorException(f"set_data_members of ReadyValid must be called with a struct of type {self.get_net_type().get_data_member_type()}")
        for name, (junction, _) in data_members.get_member_junctions().items():
            my_wire = getattr(self, name)
            my_wire <<= junction
        
    def get_data_member_type(self) -> Struct:
        if self._data_member_type is None:
            self._data_member_type = Struct()
            for name, (member, _) in self.members.items():
                if name not in ("ready", "valid"):
                    self._data_member_type.add_member(name, member)
        return self._data_member_type

    def add_member(self, name: str, member: Union[NetType, Reverse]) -> None:
        self._data_member_type = None
        if isinstance(member, Reverse) and name != "ready":
            raise SyntaxErrorException(f"ReadyValid interface {type(self)} doesn't support reverse members")
        super().add_member(name, member)
