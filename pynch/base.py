from query import QueryManager
from util import check_fields, MultiDict
from errors import (DelegationException, InheritanceException,
                    ValidationException, DocumentValidationException)
from db import FakeConnection, FakeDatabase, DB
import pymongo
import weakref
from bson.objectid import ObjectId


class Field(object):
    def __init__(self, db_field=None, required=False, default=None,
                 unique=False, unique_with=None, primary_key=False,
                 choices=None, verbose_name=None, help_text=None):
        """
        Base class for all field types. Fields are descriptors that
        manage the validation and typing of a document's attributes.
        """
        self.db_field = db_field if not primary_key else '_id'
        self.required = required
        self.default = default
        self.unique = bool(unique or unique_with)
        self.unique_with = unique_with if unique_with else []
        self.primary_key = primary_key
        self.choices = choices
        self.help_text = help_text

    def __call__(self, name, model):
        """
        Called by ModelMetaclass.

        Lipstick to avoid having to retype `name` into the field's
        constructor. Also allows us to pass in the model which owns
        the field.
        """
        self.name = name
        self.model = model
        return self

    def __get__(self, document, model=None):
        # return field instance if accessed through the class
        if document is None:
            return self

        # must convert KeyErrors to AttributeErrors
        try:
            return document.__dict__[self.name]
        except KeyError:
            raise AttributeError

    def __set__(self, document, value):
        document.__dict__[self.name] = self.validate(value)

    def __delete__(self, document):
        # must convert KeyErrors to AttributeErrors
        try:
            del document.__dict__[self.name]
        except KeyError:
            raise AttributeError

    def __str__(self):
        return self.name if hasattr(self, 'name') else self.db_field

    def _to_python(self, value):
        raise DelegationException('Define in a subclass')

    def _to_mongo(self, value):
        if self.primary_key:
            return ObjectId(value)
        return value

    def validate(self, data):
        if data is None:
            raise ValidationException(
                'NoneType is not a valid data type')
        return data


class InformationDescriptor(object):
    """
    Among other things, is responsible for generating and managing
    pynch connections to the database.

    >>> classic = Book(title='Moby Dick', author='Charles Dickens')
    >>> horror  = Book(title='The Stand', author='Steven King')
    >>> print Book._info.objects.all()  # lazy retrieval
    <generator object ...>
    """

    _connection_pool = weakref.WeakValueDictionary()

    def __init__(self, model):
        # extremely important that we retain a reference to
        # the model which owns this descriptor
        self.model = model
        self.backrefs = {}

        # do more prep
        host, port, db_name = self.model._meta.get('database')
        key = (host, port)

        # First we need to establish a connection to the db. We
        # want the option of hooking into multiple databases but
        # we don't want to unecessarily spawn connections. Therefore
        # models which declare (or inherit) the same host/port
        # values in their _meta will share a connection.
        if key not in self._connection_pool:
            connection = pymongo.MongoClient(host=host, port=port)
            # set value in the connection pool
            self._connection = \
                self._connection_pool.setdefault(key, connection)
        else:
            # ... otherwise just get what's already there
            self._connection = self._connection_pool[key]

        # Generate the actual database and collection we're going to use
        if db_name:
            self._db = self._connection[db_name]
            self._collection = getattr(self._db, model.__name__)

    def __get__(self, document, model=None):
        return self

    def __set__(self, document, value):
        # bad things happen if _info goes away
        raise NotImplementedError('Cannot overwrite _info')

    @property
    def fields(self):
        model_dict = self.model.__dict__
        return [v for v in model_dict.values() if isinstance(v, Field)]

    @property
    def objects(self):
        return QueryManager(self.model)

    @property
    def connection(self):
        return self._connection

    @property
    def db(self):
        return self._db if hasattr(self, '_db') else FakeDatabase()

    @property
    def collection(self):
        return self._collection if \
            hasattr(self, '_collection') else FakeConnection()


class ModelMetaclass(type):
    """
    For simplicity we disallow multiple inheritance among Models.

    Notice, that a subclass's _meta attribute inherits from its
    bases.  In other words, _meta attributes "stack".

    from pynch.db import DB

    class Doc_A(Model):
        _meta = {'index': ['name'],
                 'database': DB('localhost', 27017, 'test')}
        name = StringField()
        ...

    class Doc_B(Doc_A):
        _meta = {'max_size': 10000}
        ...

    Doc_B._meta will be:

        _meta = {'index': ['name'], 'max_size': 10000,
                 'database': DB('localhost', 27017, 'test')}

    Options include:
    index    := [fieldname, ...]  (default = [])
    max_size := integer           (default = 10000 bytes)

    Where `database` is a pynch.db.DB object
    host     := string            (default = 'localhost')
    port     := integer           (default = 27017)
    name     := string            (default = '')

    An interesting application, you can build a distributed,
    object oriented database like so:

    class Doc_C(Doc_B):
        _meta = {'database': DB('localhost', 27017, 'test-2')}
        field = ReferenceField(Doc_B)

    class Doc_D(Doc_B):
        _meta = {'database': DB('localhost', 27017, 'test-3')}
        field = ReferenceField(Doc_C)

    class Doc_E(Doc_B):
        _meta = {'database': DB('173.1.254.2', 27017, 'test-4')}
        field = ReferenceField(Doc_D)

    Essentially, Docs A-D are stored locally, but in different
    databases, while Doc_E is stored remotely. Every save and
    query is automatically routed to the correct database. This
    works even if subclasses of Model share references across
    different databases.

    TODO: embrace the awesomeness that is a distributed database,
          and implement a way of "meta-indexing" the databases.
    """
    def __new__(meta, name, bases, attrs):
        if len(bases) > 1:
            raise InheritanceException(
                'Multiple inheritance not allowed')

        # convert dictproxy to a dict
        base_attrs = dict(bases[0].__dict__)

        # default _meta
        _meta = {'index': [], 'max_size': 10000000,
                 'database': DB('localhost', 27017, '')}

        # pull out _meta modifier, then merge with that of current class
        _meta.update(base_attrs.pop('_meta', {}))
        _meta.update(attrs.pop('_meta', {}))

        # initialize namespace with newly updated _meta
        namespace = {'_meta': _meta}

        # finally update namespace to reflect elements in
        # the new class's __dict__
        namespace.update(attrs)

        return super(ModelMetaclass, meta).__new__(
                            meta, name, bases, namespace)

    def __init__(model, name, bases, attrs):
        # Necessary so that field descriptors can determine
        # what classes they are attached to.
        for fieldname, field in attrs.items():
            if isinstance(field, Field):
                field(fieldname, model)

        # information descriptor allows class level access to
        # orm functionality
        model._info = InformationDescriptor(model)
        # DON'T FORGET TO CALL type's init
        super(ModelMetaclass, model).__init__(name, bases, attrs)


class Model(object):
    __metaclass__ = ModelMetaclass

    def __init__(self, **values):
        super(Model, self).__init__()
        # setattr must be called to activate the descriptors,
        # rather than update the document's __dict__ directly
        for k, v in values.items():
            setattr(self, k, v)

    @property
    def pk(self):
        for field in self._info.fields:
            if field.primary_key:
                return ObjectId(getattr(self, field.name))

        return self._id if hasattr(self, '_id') else None

    def to_mongo(self):
        self.validate()
        # lambda fcn that returns tuples of (db_field, document field value)
        _to_mongo = lambda field: (field.db_field or field.name,
                                   field._to_mongo(getattr(self, field.name)))
        # build a mongo compatible dictionary
        mongo = dict(_to_mongo(field) for field in self._info.fields)

        return mongo

    @classmethod
    def to_python(cls, mongo):
        python_fields = {}
        for field in cls._info.fields:
            python_fields[field.name] = field._to_python(mongo[field.db_field])

        return cls(**python_fields)

    def validate(self):
        # validate fields, collecting exceptions in a dictionary
        exceptions = MultiDict(check_fields(self))

        # return the document instance on success
        # (ie exceptions is empty)
        if not exceptions:
            return self

        # traceback provides a detailed breakdown of a document's
        # validation errors by field
        raise DocumentValidationException(
            'Document failed to validate', exceptions=exceptions)

    def save(self, *args, **kwargs):
        self._info.collection.insert(self.to_mongo())
