from collections import namedtuple


class FakeConnection(object):
    pass


class FakeDatabase(object):
    pass


DB = namedtuple('DB', 'host port name')
