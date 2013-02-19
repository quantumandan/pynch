from pynch.query import QueryManager
from pynch.db import MockDatabase, MockConnection, DB
import pymongo
from bson.dbref import DBRef
from bson.objectid import ObjectId
import weakref
import inspect
from pynch.errors import *
from pynch.util.misc import MultiDict, dir_, raise_
from pynch.util.field_utils import (check_fields, field_to_mongo_tuple,
                                    get_field_value_or_default)


class Field(object):
    def __new__(cls, *args, **modifiers):
        """
        necessary so that complex fields and reference fields
        can import and bind the correct classes
        """
        field = super(Field, cls).__new__(cls)
        outermost_frame = inspect.stack()[-1][0]
        field._context = outermost_frame.f_locals.get('__name__', '')
        return field

    def __init__(self, db_field=None, required=False, default=None,
                 unique=False, unique_with=None, primary_key=False,
                 choices=None, help_text=None):
        """
        Base class for all field types. Fields are descriptors that
        manage the validation and typing of a document's attributes.
        """
        # primary keys are required
        self.db_field = db_field if not primary_key else '_id'
        self.required = required if not primary_key else True
        self.primary_key = primary_key
        # default's get called when no corresponding attr exists
        # in the document's __dict__
        self.default = default
        # caution, marking a lot of fields as unique will cause
        # you to take a performance hit when validating
        self.unique = unique
        # since unique_with can be either a string or a list
        # of strings, we must check and convert as needed
        self.unique_with = unique_with if unique_with else []
        self.choices = choices
        self.help_text = help_text

    def set(self, name, model):
        """
        Lipstick to avoid having to retype `name` into the field's
        constructor. Also allows us to pass in the model which owns
        the field.
        """
        self.name = name
        self.model = model

    def __get__(self, document, model=None):
        # return field instance if accessed through the class
        if document is None:
            return self
        # converts KeyErrors to AttributeErrors in the event
        # that the value is not found in the document and the
        # default is None
        return get_field_value_or_default(document, self)

    def __set__(self, document, value):
        document.__dict__[self.name] = self.validate(value)

    def __delete__(self, document):
        # convert KeyErrors to AttributeErrors
        try:
            del document.__dict__[self.name]
        except KeyError:
            raise AttributeError

    def __str__(self):
        field_unset_msg = '<%s %s field object not set>' % (type(self), id(self))
        return getattr(self, 'name', field_unset_msg)

    def to_mongo(self, value):
        # traverses the validation hierarchy top down
        mongo = self.validate(value)

        # primary key must be of type `ObjectId`
        if self.primary_key:
            return ObjectId(mongo) if not \
                isinstance(mongo, ObjectId) else mongo

        # already validated and not a primary key
        return mongo

    def to_python(self, value):
        raise DelegationException('Define in a subclass')

    def validate(self, value):
        raise DelegationException('Define in a subclass')

    def is_set(self):
        return hasattr(self, 'name')


class ObjectIdField(Field):
    def set(self, name, model):
        super(ObjectIdField, self).set(name, model)

        for field in model._info.fields:
            if field.primary_key:
                assert (name == field.name) or \
                       (field.db_field == '_id')

    def to_mongo(self, value):
        # traverses the validation hierarchy top down
        mongo = self.validate(value)

        # primary key must be of type `ObjectId`
        if self.primary_key:
            return ObjectId(mongo) if not \
                isinstance(mongo, ObjectId) else mongo

    def to_python(self, value):
        return value

    def validate(self, value):
        return value


class InformationDescriptor(object):
    """
    Among other things, is responsible for generating and managing
    pynch connections to the database.

    Most of your time will be spent accessing things like `objects`

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
        model_name = self.model.__name__
        self.collection = getattr(self.db, model_name)

    def __get__(self, document, model=None):
        return self

    def __set__(self, document, value):
        # bad things happen if _info goes away
        raise NotImplementedError('Cannot overwrite _info')

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
        return [v for v in dir_(self.model).values() if isinstance(v, Field)]


class ModelMetaclass(type):
    def __new__(meta, name, bases, attrs):
        if len(bases) > 1:
            raise InheritanceException(
                'Multiple inheritance not allowed')

        # convert dictproxy to a dict
        base_attrs = dict(bases[0].__dict__)

        # default _meta
        _meta = {'index': [], 'max_size': 10000000, 'database': DB()}

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
                assert fieldname != 'pk'
                field.set(fieldname, model)

        # information descriptor allows class level access to
        # orm functionality
        model._info = InformationDescriptor(model)
        # DON'T FORGET TO CALL type's init
        super(ModelMetaclass, model).__init__(name, bases, attrs)


class Model(object):
    """
    For simplicity we disallow multiple inheritance among Models.

    Notice, that a subclass's _meta attribute inherits from its
    bases.  In other words, _meta attributes "stack".

    from pynch.db import DB

    class Doc_A(Model):
        _meta = {'index': ['name'],
                 'database': DB('test', 'localhost', 27017)}
        name = StringField()
        ...

    class Doc_B(Doc_A):
        _meta = {'max_size': 10000}
        ...

    Doc_B._meta will be:

        _meta = {'index': ['name'], 'max_size': 10000,
                 'database': DB('test', 'localhost', 27017)}

    Options include,
    index    := [fieldname, ...]  (default = [])
    max_size := integer           (default = 10000 bytes)

    Where `database` is a pynch.db.DB object,
    name     := string            (default = '')
    host     := string            (default = 'localhost')
    port     := integer           (default = 27017)

    TODO:
    An interesting application, you can build a distributed,
    NoSQL database like so:

    class Doc_C(Doc_B):
        _meta = {'database': DB('test-2', 'localhost', 27017)}
        field = ReferenceField(Doc_B)

    class Doc_D(Doc_B):
        _meta = {'database': DB('test-3', 'localhost', 27017)}
        field = ReferenceField(Doc_C)

    class Doc_E(Doc_B):
        _meta = {'database': DB('test-4', '173.1.2.5', 27017)}
        field = ReferenceField(Doc_D)

    Essentially, Docs A-D are stored locally, but in different
    databases, while Doc_E is stored remotely. Every save and
    query is automatically routed to the correct database. This
    works even if subclasses of Model share references across
    the different databases.
    """
    __metaclass__ = ModelMetaclass

    def __init__(self, *castable, **values):
        super(Model, self).__init__()

        # allows up and down casting
        if castable:
            values.update(castable[0].__dict__)

        for k, v in values.items():
            # deserialize DBRefs if possible
            if isinstance(v, DBRef):
                cls = self.__class__
                v = getattr(cls, k).to_python(v) if hasattr(cls, k) else \
                        raise_(DocumentValidationException('Cannot resolve dbref'))

            # setattr must be called to activate the descriptors,
            # rather than update the document's __dict__ directly
            setattr(self, k, v)

        # everything must have some form of id
        if not self.pk:
            self._id = ObjectId()

    @property
    def pk(self):
        """
        finds the model's primary key, if any
        """
        for field in self._info.fields:
            if field.primary_key:
                return getattr(self, field.name)
        return self._id if hasattr(self, '_id') else None

    def to_mongo(self):
        # start at the top of the hierarchy and work your way down
        self.validate()

        # build a mongo compatible dictionary
        mongo = dict(field_to_mongo_tuple(self, field) \
                            for field in self._info.fields)
        return mongo

    @classmethod
    def to_python(cls, mongo):
        python_fields = {}

        for field in cls._info.fields:
            mongo_value = mongo[field.db_field or field.name]
            # (secretly) traverse the document hierarchy
            python_fields[field.name] = field.to_python(mongo_value) if \
                                             mongo_value is not None else None

        # cast the resulting dict to this particular model type
        return cls(**python_fields)

    def validate(self):
        assert self.pk, 'Document is missing a primary key'
        # validate fields, collecting exceptions in a dictionary
        exceptions = MultiDict(check_fields(self))

        # return the document on success (ie exceptions is empty)
        if not exceptions:
            return self

        # traceback provides a detailed breakdown of a document's
        # validation errors by field
        raise DocumentValidationException(
            'Document failed to validate', exceptions=exceptions)

    def update(self, spec, **kwargs):
        self._info.collection.update(spec, self.to_mongo(), **kwargs)

    def insert(self, *args, **kwargs):
        self._info.collection.insert(self.to_mongo(), **kwargs)

    def save(self, **kwargs):
        self._info.collection.save(self.to_mongo(), **kwargs)

    def delete(self):
        oid = ObjectId(self.pk) if self.pk else None
        if oid is None:
            raise Exception('Cant delete documents which '
                            'have no _id or primary key')
        self._info.collection.remove(oid)

    @classmethod
    def find_one(cls):
        return cls.to_python(cls._info.collection.find_one())

    @classmethod
    def find(cls, **spec):
        return cls._info.collection.find(**spec)
