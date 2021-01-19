from typing import Any, Iterator, Optional
from collections import deque
from threading import RLock

class Stack(object):
    def __init__(self):
        self.queue = deque()
        self.lock = RLock()
    def top(self) -> Any:
        with self.lock:
            return self.queue[-1]
    #
    def push(self, item: Any) -> 'Stack.Context':
        with self.lock:
            self.queue.append(item)
            return Stack.Context(self)
    def pop(self) -> Any:
        with self.lock:
            return self.queue.pop()
    def peek(self, idx: int) -> Any:
        with self.lock:
            return self.queue[-idx-1]
    def is_empty(self) -> bool:
        with self.lock:
            return len(self.queue) == 0
    def __iter__(self) -> Iterator:
        return iter(self.queue)
    def __len__(self) -> int:
        with self.lock:
            return len(self.queue)
    
    class Context(object):
        def __init__(self, parent: 'Stack'):
            self.parent = parent
        def __enter__(self):
            self.parent.lock.__enter__()
            return self
        def __exit__(self, type, value, traceback) -> Optional[bool]:
            self.parent.pop()
            return self.parent.lock.__exit__(self, type, value, traceback)
        def top(self) -> Any:
            return self.parent.top()
        def peek(self, idx: int) -> Any:
            return self.parent.peek(idx)
        def __len__(self) -> int:
            return len(self.parent)
