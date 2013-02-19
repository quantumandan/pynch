from collections import namedtuple


_DB_tuple = namedtuple('DB', 'name host port')


class DB(_DB_tuple):
    def __new__(cls, *args, **kwargs):
        if not args:
            args += (kwargs.pop('name', ''),)
            args += (kwargs.pop('host', 'localhost'),)
            args += (kwargs.pop('port', 27017),)
        return super(DB, cls).__new__(cls, *args)


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
