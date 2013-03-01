from pynch.query import QueryManager
from pynch.db import MockDatabase, MockConnection, DB
import pymongo
import weakref
import inspect
from bson.objectid import ObjectId
from pynch.errors import *
from pynch.util.misc import MultiDict, dir_
from pynch.util.field_utils import (check_fields, field_to_save_tuple,
                                    get_field_value_or_default)


class Field(object):
    def __new__(cls, *args, **modifiers):
        """
        Necessary so that reference fields can import and
        bind the correct classes
        """
        field = super(Field, cls).__new__(cls)
        frame = inspect.stack()[-1][0]  # outermost frame
        field._context = frame.f_locals.get('__name__', '')
        return field

    def __init__(self, db_field=None, required=False, default=None,
                 unique=False, unique_with=None, primary_key=False,
                 choices=None, help_text=None, *args, **kwargs):
        """
        Base class for all field types. Fields are descriptors that
        manage the validation and typing of a document's attributes.

        Fields marked as a primary key will take precedence over any
        `_id` field set on the document.
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

    def is_set(self):
        return hasattr(self, 'name')

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
        field_unset_msg = '<%s %s field object (not set)>' % (type(self), id(self))
        return getattr(self, 'name', field_unset_msg)

    def to_save(self, value):
        raise DelegationException('Define in a subclass')

    def to_python(self, value):
        raise DelegationException('Define in a subclass')

    def validate(self, value):
        raise DelegationException('Define in a subclass')


class FieldProxy(property):
    """
    Is used to add "computed" fields to a document instance.
    To use, define a getter and a setter.  An example of a
    useful idiom:

    >>> import random
    >>> get_X = lambda self: \
    ...     self.__dict__.setdefault('_value', random.random())
    >>> set_X = lambda self, value: \
    ...     self.__dict__.__setitem__('_value', value)
    >>> proxy = FieldProxy(get_X, set_X, help_text='I am computed')
    >>> print proxy.help_text
    I am computed
    >>> class MyModel(Model):
    ...    pass
    >>> MyModel.computed_field = proxy

    then,

    >>> document = MyModel()
    >>> print document.computed_field
    0.0821333  # some random number
    >>> print document.computed_field
    0.0821333  # same number, default has been set
    >>> document.computed_field = 2
    >>> print document.computed_field
    2
    """
    def __init__(self, fget=None, fset=None,
                 fdel=None, doc=None, **kwargs):
        super(FieldProxy, self).__init__(fget, fset, fdel, doc)
        self.__dict__.update(kwargs)

    def to_python(self, value):
        return value

    def validate(self, value):
        return value


class PrimaryKeyProxy(FieldProxy):
    def __init__(self):
        def get_ID(doc):
            return doc.__dict__.setdefault('_id', ObjectId())
        def set_ID(doc, value):
            doc.__dict__['_id'] = value
        super(PrimaryKeyProxy, self).__init__(
                        get_ID, set_ID, primary_key=True)


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
        return self

    def __set__(self, document, value):
        # bad things happen if _pynch goes away
        raise NotImplementedError('Cannot overwrite _pynch')

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
        items = dir_(self.model).items()
        return [v for k, v in items if isinstance(v, Field)]


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
                # `pk`, `validate`, `save`, `delete`, `search`, and
                # `get` are reserved for pynch, everything else is
                # fair game
                assert fieldname not in ('pk', 'validate', 'to_python',
                                        'save', 'delete', 'get')
                field.set(fieldname, model)

        # Everything must have an `_id`. If none is attached, then
        # dynamically create one using a FieldProxy
        if not hasattr(model, '_id'):
            model._id = PrimaryKeyProxy()

        # information descriptor allows class level access to
        # orm functionality
        model._pynch = InformationDescriptor(model)
        # DON'T FORGET TO CALL type's init
        super(ModelMetaclass, model).__init__(name, bases, attrs)


class Model(object):
    """
    For simplicity we disallow multiple inheritance among Models.

    Notice, that a subclass's _meta attribute inherits from its
    bases.  In other words, _meta attributes "stack".
    """
    __metaclass__ = ModelMetaclass

    def __init__(self, *castable, **values):
        super(Model, self).__init__()

        # collect all validation failures
        exceptions = MultiDict()

        for k, v in values.items():
            # setattr must be called to activate the descriptors, rather
            # than update the document's __dict__ directly
            try:
                # if v is None then no acceptable value was, for this
                # field, was passed into the model's constructor
                if v is not None:
                    setattr(self, k, v)
            except Exception as e:
                exceptions.append(k, e)

        if exceptions:
            raise DocumentValidationException(
                'Could not reconstruct document', exceptions=exceptions)

        # allows up and down casting
        if castable:
            castable = castable[0]
            # `castable` must either belong to a subclass of the
            # current model, or the current model must be a sublcass
            # of castable's model
            assert (isinstance(castable, type(self)) or \
                    isinstance(self, type(castable)))
            self.__dict__.update(castable.__dict__)

    @property
    def pk(self):
        """
        finds the model's primary key, if any
        """
        for field in self._pynch.fields:
            if field.primary_key and hasattr(self, field.name):
                return getattr(self, field.name)
        # default to _id, which either exists on the document or
        # is the result of a computed field (ie a FieldProxy)
        return self._id

    @classmethod
    def to_python(cls, mongo):
        python_fields = {}
        for field in cls._pynch.fields:
            # rememeber mongo info is stored with key `field.db_field`
            # if it is different from `field.name`
            fieldname = field.db_field or field.name
            # and that field might not be present if a no attribute
            # value was passed in before the document was saved
            mongo_value = mongo[fieldname] if \
                        fieldname in mongo else field.default
            # (secretly) traverse the document hierarchy top down
            python_fields[field.name] = field.to_python(mongo_value)
        # cast the resulting dict to this particular model type
        return cls(**python_fields)

    def validate(self):
        # assert self.pk, 'Document is missing a primary key'
        # validate fields, collecting exceptions in a dictionary
        exceptions = MultiDict(check_fields(self))

        # return the document on success (ie exceptions is empty)
        if not exceptions:
            return self

        # traceback provides a detailed breakdown of a document's
        # validation errors by field
        raise DocumentValidationException(
            'Document failed to validate', exceptions=exceptions)

    def save(self, **kwargs):
        # start at the top of the hierarchy and work your way down
        document = self.validate()

        # build a mongo compatible dictionary
        mongo = dict(field_to_save_tuple(document, field) \
                                for field in self._pynch.fields)
        mongo.setdefault('_id', self.pk)
        self._pynch.collection.save(mongo, **kwargs)
        return document

    def delete(self):
        oid = self.pk if self.pk else None
        if oid is None:
            raise Exception('Cant delete documents which '
                            'have no _id or primary key')
        self._pynch.collection.remove(oid)

    def get(self, search_term, obj=None, query_filter=None):
        """
        TODO: implement results filtering

        class Petal(Model):
            color = StringField()
        class Flower(Model):
            petals = ListField(ReferenceField(Petal))
        class Garden(Model):
            flowers = ListField(ReferenceField(Flowers))
        ...
        # returns a generator with all the colors of all
        # the petals, of all the flowers in the garden
        >>> garden.get('flowers.petals.color')
        """
        # set root
        obj = obj or self
        # split dot-notated search term, first element is root
        terms = search_term.split('.')
        T, new_T = terms.pop(0), '.'.join(terms)
        if not T:
            yield obj
            raise StopIteration
        # get the field value at the current level
        obj = [getattr(obj, T)] if not \
                isinstance(obj, (list, set)) else (getattr(o, T) for o in obj)
        # in PY3.3 and greater, this is a perfect example
        # of when to use the `yield from` syntax
        for element in obj:
            for found in self.get(new_T, element):
                yield found
