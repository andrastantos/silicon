from typing import Tuple, Union, Any, Dict, Set, Optional, Callable

from .port_type import PortType
from .tracer import no_trace
from .module import Module, InlineBlock
from .exceptions import SyntaxErrorException

class Sequence(PortType):
    """
    Sequence ports are an abstract representation of ports whos values are python lists.
    
    During simulation these ports act as normal ports, but during RTL generation,
    they generate structs with members for each entry in the list with the name of
    element_<X>.

    Sequence ports can be accessed, using the [] notation, similar to python lists.

    Sequence ports can be bound to vector ports:
        my_entity.vector_input = [a,b,c]
    In this case, the sequence gets flattened, provided all elements in the sequence
    are either of a compatible type as the vectors element type or recursive seqeuences
    of the same. In other words, this works:

    my_entity.vector_input = [1,3,1,[5,[3,2],5,11],1]

    if vector_input has the type of Vector(Unsigned(16)), the result is going to be that 
    vector_input gets the value of [1,3,1,5,3,2,5,11,1].

    if vector_input has the type of Unsigned(32), the result is going to be the
    concatenation of all the bit-patterns as Numbers are also Vectors (well, VectorBases).

    if vector_input is Unsigned(32) but it is assigned [1,3,-1] for example, the assignment
    fails as one of the members is Signed.
    """
