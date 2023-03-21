import collections

class OrderedSet(collections.abc.MutableSet):
    def __init__(self, iterable=None):
        if iterable is None:
            self.map = dict()
        else:
            self.map = dict((item, None) for item in iterable)

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map.keys()

    def add(self, key):
        self.map[key] = None

    def remove(self, key):
        del self.map[key]

    def discard(self, key):
        try:
            del self.map[key]
        except KeyError:
            pass

    def __contains__(self, item):
        return item in self.map.keys()

    def __iter__(self):
        return self.map.keys().__iter__()

    def __reversed__(self):
        return self.map.keys().__reversed__()

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)

    def clear(self):
        self.map.clear()

    def __ior__(self, other):
        if isinstance(other, OrderedSet):
            self.map.update(other.map)
        else:
            for x in other:
                self.add(x)
        return self

class A(object):
    def __init__(self):
        self.a = 42

def t():
    a = (A(), A(), A())
    return OrderedSet(a)

if __name__ == '__main__':
    print(OrderedSet('abracadaba'))
    print(OrderedSet('simsalabim'))
    x = t()
    for b in x:
        print(b.a)


