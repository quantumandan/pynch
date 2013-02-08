

class InheritanceException(TypeError):
    pass


class DelegationException(InheritanceException, NotImplementedError):
    pass
