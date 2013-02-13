from collections import namedtuple


_DB_tuple = namedtuple('DB', 'name host port')


def DB(*args, **kwargs):
    if not args and not kwargs:
        return _DB_tuple('', 'localhost', 27017)
    return _DB_tuple(*args, **kwargs)


class MockConnection(object):
    def __init__(self, host, port):
        pass


class MockCollection(object):
    pass


class MockDatabase(object):
    def __init__(self, conn):
        self.conn = conn

    def __getattr__(self, key):
        return type(key, (MockCollection,), {})
