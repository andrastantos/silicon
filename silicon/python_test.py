class A(object):
    def __getitem__(self, *args, **kwargs):
        print("__getitem__ is called with :")
        print("\t", ",".join(str(arg) for arg in args))
        print("\t", ",".join(f"{key}:{value} " for key, value in kwargs.items()))
        return None

class _Generic(object):
    Specializations = []

    @classmethod
    def __getitem__(cls, *args):
        name = f"Generic_{len(cls.Specializations)}"
        Specialized = type(name, (cls,), {"specials": tuple(args)})
        cls.Specializations.append(Specialized)
        return Specialized

    def __init__(self, value = None):
        self.value = value

    def __str__(self):
        if hasattr(self, "specials"):
            return(f"[{type(self)} - " + ",".join(str(special) for special in self.specials) + f"] - {self.value}")
        else:
            return(f"[{type(self)} - GENERIC" + f"] - {self.value}")

Generic = _Generic()

#g = Generic() - fails because of no specialization is given
s1 = Generic[12]()
s2 = Generic[42]("Hi!")

print(s1)
print(s2)