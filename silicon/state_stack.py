from typing import Optional

class StateStackElement(object):
    _stack = []
    _object_stacks = {}
    
    def __init__(self):
        pass
    
    def __enter__(self) -> 'StateStackElement':
        if self.__class__ not in self._object_stacks:
            self._object_stacks[self.__class__] = []
        self._object_stacks[self.__class__].append(self)
        self._stack.append(self)
        return self
    
    def __exit__(self, exception_type, exception_value, traceback):
        assert self._object_stacks[self.__class__][-1] is self
        assert self._stack[-1] is self
        self._stack.pop()
        self._object_stacks[self.__class__].pop()

    @classmethod
    def top(cls) -> Optional['StateStackElement']:
        if cls not in cls._object_stacks:
            return None
        if len(cls._object_stacks[cls]) == 0:
            return None
        return cls._object_stacks[cls][-1]

if __name__ == "__main__":
    class A(StateStackElement):
        pass
        def __str__(self):
            return "A"

    class B(StateStackElement):
        def __init__(self, param):
            self.param = param
        def __str__(self):
            return f"B {self.param}"

    with A():
        print(A.top())

        with B(1):
            print(A.top())
            print(B.top())
        print(A.top())
        print(B.top())
        with B(2):
            with B(3):
                print(B.top())
            print(B.top())
