from .composite import Interface, Reverse, Struct
from .number import logic
from collections import OrderedDict
from typing import Dict, Tuple, Union
from .net_type import behavior, NetType
from .port import Junction
from .utils import get_composite_member_name

class ReadyValid(Interface):
    ready = Reverse(logic)
    valid = logic

    @behavior
    def get_data_members(self) -> Dict[Tuple[str], Junction]:
        ret_val = OrderedDict()
        for names, (member, reverse) in self.get_all_member_junctions_with_names(add_self=False).items():
            if names not in (("valid",), ("ready", )):
                if reverse:
                    raise SyntaxErrorException(f"ReadyValid interface doesn't support reversed data member. Member {get_composite_member_name(names)} is reversed in {self}")
                ret_val[names] = member
        return ret_val

    def add_member(self, name: str, member: Union[NetType, Reverse]) -> None:
        if isinstance(member, Reverse) and name != "ready":
            raise SyntaxErrorException(f"ReadyValid interface {type(self)} doesn't support reverse members")
        super().add_member(name, member)
