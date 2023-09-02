# Contains a simple generic definition for the APB bus.
#     https://developer.arm.com/documentation/ihi0024/latest/

from .composite import Interface, Reverse, GenericMember
from .number import logic
from .net_type import NetType

class ApbBaseIf(Interface):
    pwrite = logic
    psel = logic
    penable = logic
    pready = Reverse(logic)

    paddr = GenericMember

_apb_if_cache = {}

def ApbIf(data_type: NetType) -> type:
    """Creates and returns an APB interface type for the specified datatype.

    :param data_type: The NetType for the prdata and pwdata members of the APB interface

    :return: Returns an ApbBaseIf sub-class with the properly typed prdata and pwdata members.
    """

    if data_type in _apb_if_cache:
        return _apb_if_cache[data_type]
    ApbIfType = type(f"ApbIf_{data_type.get_type_name}", (ApbBaseIf,), {})
    ApbIfType.add_member("pwdata", data_type)
    ApbIfType.add_member("prdata", Reverse(data_type))
    _apb_if_cache[data_type] = ApbIfType
    return ApbIfType

