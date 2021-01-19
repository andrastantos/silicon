#!/usr/bin/python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__),".."))

from typing import *

from silicon import *
from test_utils import *

def test_common_superclass():
    class A(object):
        pass
    class B(object):
        pass
    class A1(A):
        pass
    class A2(A):
        pass
    class A21(A1, A2):
        pass
    class A21B(A21, B):
        pass
    class B1(B):
        pass

    assert common_superclass(A(),B()) is object
    assert common_superclass(A(),A1()) is A
    assert common_superclass(A1(),A21()) is A1
    assert common_superclass(A21B(),A1(),B1()) is object

if __name__ == "__main__":
    test_common_superclass()
