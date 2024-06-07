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


    class ApbAdaptor(GenericModule):
        input_port = Input()
        output_port = Output()

        def construct(self, output_type):
            self.output_port.set_net_type(output_type)

        def body(self):
            self.output_port.pwrite <<= self.input_port.pwrite
            self.output_port.psel <<= self.input_port.psel
            self.output_port.penable <<= self.input_port.penable
            self.output_port.paddr <<= self.input_port.paddr
            self.output_port.pwdata <<= self.input_port.pwdata
            self.input_port.prdata <<= self.output_port.prdata
            self.input_port.pready <<= self.outpot_port.pready

    @classmethod
    def adapt_from(cls, input: Any, implicit: bool, force: bool) -> Any:
        if not isinstance(input, ApbBaseIf):
            return AdaptTypeError
        if input.get_members()["prdata"].get_net_type() is not cls.get_members()["prdata"].get_net_type():
            return AdaptTypeError
        if input.get_members()["pwdata"].get_net_type() is not cls.get_members()["pwdata"].get_net_type():
            return AdaptTypeError
        if cls.get_members()["paddr"].get_net_type() is GenericMember:
            return ApbBaseIf.ApbAdaptor(cls)
        if input.paddr.get_net_type() is not cls.pwdata.get_net_type():
            return AdaptTypeError

_apb_if_cache = {}

def ApbIf(data_type: NetType, addr_type: NetType = None) -> type:
    """Creates and returns an APB interface type for the specified datatype.

    :param data_type: The NetType for the prdata and pwdata members of the APB interface

    :return: Returns an ApbBaseIf sub-class with the properly typed prdata and pwdata members.
    """

    key = (data_type, addr_type)
    if key in _apb_if_cache:
        return _apb_if_cache[key]
    ApbIfType = type(f"ApbIf_{data_type.get_type_name}", (ApbBaseIf,), {})
    ApbIfType.add_member("pwdata", data_type)
    ApbIfType.add_member("prdata", Reverse(data_type))
    if addr_type is not None:
        ApbIfType.add_member("paddr", addr_type)
    else:
        ApbIfType.add_member("paddr", GenericMember)
    _apb_if_cache[key] = ApbIfType
    return ApbIfType

