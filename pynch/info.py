from pynch.query import QueryManager
from pynch.db import MockDatabase, MockConnection
import pymongo
import weakref
from pynch.util import dir_
from pynch.errors import ConnectionException, QueryException
from pynch.fields import Field


class InformationDescriptor(object):
    """
    Among other things, is responsible for generating and managing
    pynch connections to the database.
    """

    _connection_pool = weakref.WeakValueDictionary()

    def __init__(self, model):
        # extremely important that we retain a reference to
        # the model which owns this descriptor
        self.model = model
        self.backrefs = {}
        self.primary_key_field = None

        # do some more prep
        db_name, host, port = self.model._meta.get('database')
        try:
            self.connection = self.connect(host, port)
        except ConnectionException:
            self.connection = MockConnection(host, port)

        # generate the actual database if it is named, otherwise
        # create an in memory mockup
        self.db = self.connection[db_name] if \
                        db_name else MockDatabase(self.connection)

        # and make the collection we're going to use
        self.collection = getattr(self.db, self.model.__name__)

    def __get__(self, document, model=None):
        # always returns itself
        return self

    def __set__(self, document, value):
        # bad things happen if pynch goes away
        raise NotImplementedError('Cannot overwrite pynch')

    def connect(self, host, port):
        """
        We need to establish a connection to the db and want the
        option of hooking into multiple databases but don't want
        to unecessarily spawn connections. Therefore models which
        declare (or inherit) the same host and port values in their
        respective _meta's will share a connection.
        """
        key = (host, port)
        if key not in self._connection_pool:
            # build the connection
            connection = pymongo.MongoClient(host=host, port=port)
            # set value in the connection pool
            return self._connection_pool.setdefault(key, connection)
        # otherwise just get what's already there
        return self._connection_pool[key]

    @property
    def objects(self):
        return QueryManager(self.model)

    @property
    def fields(self):
        values = dir_(self.model).values()
        return tuple(v for v in values if isinstance(v, Field))

    def _raw_find(self, dictionary):
        for fieldname in dictionary.keys():
            field = getattr(self.model, fieldname)
            if field.primary_key and field.name != '_id':
                dictionary['_id'] = dictionary.pop(fieldname)
        return self.collection.find(dictionary)

    def find(self, dictionary):
        results = self._raw_find(dictionary)
        if results is not None:
            return (self.model.to_python(x) for x in results)
        raise QueryException('No matching documents')

    def get(self, **kwargs):
        results = self._raw_find(kwargs)
        # query returns nothing
        if results is None:
            raise QueryException('No matching documents')
        # whoops query doesnt have unique result
        if results.count() > 1:
            raise QueryException('Multiple objects fouund')

        return self.model.to_python(results.next())
