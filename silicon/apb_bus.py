# Contains a simple generic definition for the APB bus.
#     https://developer.arm.com/documentation/ihi0024/latest/

from .composite import Interface, Reverse, GenericMember
from .number import logic
from .net_type import NetType
from silicon import *
from silicon.exceptions import AdaptTypeError

class ApbBaseIf(Interface):
    """
    APB signalling

                <-- read -->      <-- write ->
        CLK     \__/^^\__/^^\__/^^\__/^^\__/^^\__/^^\__/
        psel    ___/^^^^^^^^^^^\_____/^^^^^^^^^^^\______
        penable _________/^^^^^\___________/^^^^^\______
        pready  ---------/^^^^^\-----------/^^^^^\------
        pwrite  ---/^^^^^^^^^^^\-----\___________/------
        paddr   ---<===========>-----<===========>------
        prdata  ---------<=====>------------------------
        pwdata  ---------------------<===========>------
    """
    pwrite = logic
    psel = logic
    penable = logic
    pready = Reverse(logic)



_apb_if_cache = {}

def ApbIf(data_type: NetType, addr_type: NetType = None) -> type:
    """Creates and returns an APB interface type for the specified datatype.

    :param data_type: The NetType for the prdata and pwdata members of the APB interface

    :return: Returns an ApbBaseIf sub-class with the properly typed prdata and pwdata members.
    """

    key = (data_type, addr_type)
    if key in _apb_if_cache:
        return _apb_if_cache[key]
    type_name = f"ApbIf_D[{data_type.get_type_name()}]" if addr_type is None else f"ApbIf_D[{data_type.get_type_name()}]_A[{addr_type.get_type_name()}]"
    ApbIfType = type(type_name, (ApbBaseIf,), {})
    ApbIfType.add_member("pwdata", data_type)
    ApbIfType.add_member("prdata", Reverse(data_type))
    if addr_type is not None:
        ApbIfType.add_member("paddr", addr_type)
    else:
        ApbIfType.add_member("paddr", GenericMember)
    _apb_if_cache[key] = ApbIfType
    return ApbIfType

