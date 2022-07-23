import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / ".."))
sys.path.append(str(Path(__file__).parent / ".."/ "unit_tests"))

from typing import *

from silicon import *
from test_utils import *

iadd_call_cnt = 0

class BehaviorBase(object):
    def __init__(self):
        self.base_attribute = "basic"
    def say_hello(self):
        print("oh, hello!")

class BehavingType(NetType):
    class Behaviors(BehaviorBase):
        class_member = 42
        def __init__(self, prop_value):
            super().__init__()
            self.prop_value = prop_value
            self.regular_value = "normal"
        def behavior_method(self, x):
            return x+1
        @property
        def prop(self):
            return self.prop_value
        @prop.setter
        def prop(self, x):
            self.prop_value = x

        def __iadd__(self, other):
            globals()['iadd_call_cnt'] += 1
            print(f"__iadd___ called with __class__: {__class__}")
            super().say_hello()
            return self

    @classmethod
    def get_behaviors(cls):
        return cls.Behaviors("hello")


def test_main():
    j1 = Junction()
    i1 = Input()
    o1 = Output()
    w1 = Wire()
    j2 = Junction(BehavingType)
    i2 = Input(BehavingType)
    o2 = Output(BehavingType)
    w2 = Wire(BehavingType)

    print(f"o2.class_member: {o2.class_member}")
    w2 += w1
    assert iadd_call_cnt == 1
    i2 += w2
    assert iadd_call_cnt == 2
    w1.set_net_type(BehavingType)
    w1 += w2
    assert iadd_call_cnt == 3
    assert w2.class_member == 42
    try:
        print(j1.class_member)
        assert False, "This should have failed!"
    except AttributeError:
        pass
    assert w1.regular_value == "normal"
    w1.regular_value = "not so much anymore"
    assert w1.regular_value == "not so much anymore"
    assert w2.regular_value == "normal"
    assert w1.prop == "hello"
    w1.prop = "goodbye"
    assert w1.prop == "goodbye"
    assert w2.prop == "hello"
    assert w2.base_attribute == "basic"
if __name__ == "__main__":
    test_main()

