from query import QueryManager
from util import check_fields, MultiDict
from errors import (DelegationException, InheritanceException,
                    ValidationException, DocumentValidationException)


class Field(object):
    def __init__(self, db_field=None, required=False, default=None,
                 unique=False, unique_with=None, primary_key=False,
                 choices=None, verbose_name=None, help_text=None):
        """
        Base class for all field types. Fields are descriptors that
        manage the validation and typing of a document's attributes.

        Fields whose name starts with a leading underscore are "hidden"
        These fields are not available through `.info.fields` and must
        be explicitly dealt with (the only exception is `_id`)
        """
        self.db_field = db_field if not primary_key else '_id'
        self.required = required
        self.default = default
        self.unique = bool(unique or unique_with)
        self.unique_with = list(unique_with) if unique_with else []
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

    def _to_python(self, *args, **kwargs):
        raise DelegationException('Define in a subclass')

    def _to_mongo(self, *args, **kwargs):
        raise DelegationException('Define in a subclass')

    def validate(self, data):
        if data is None:
            raise ValidationException(
                'NoneType is not a valid data type')
        return data


class InformationDescriptor(object):
    """
    class Book(Model):
        _meta = {'index': ['title', 'author']}
        title = StringField()
        author = StringField()
        chapters = ListField(ReferenceField('Chapter'))

        def __str__(self):
            return self.title

    >>> classic = Book(title='Moby Dick', author='Charles Dickens')
    >>> horror  = Book(title='The Stand', author='Steven King')

    Note, `_info.objects.all()` returns a generator (lazy retrieval)

    >>> print [str(book) for book in Book._info.objects.all()]
    ['Moby Dick', 'The Stand']
    """
    def __init__(self, model):
        self.model = model
        self.backrefs = {}
        # self.collection = model._meta.collection

    def __get__(self, document, model=None):
        return self

    def __set__(self, document, value):
        raise NotImplementedError('Cannot overwrite _info')

    @property
    def fields(self):
        # remember that fields with a leading underscore are "hidden"
        # unless the field's name is `_id`
        return [v for k, v in self.model.__dict__.items() \
                    if isinstance(v, Field) and \
                        (not k.startswith('_') or k is '_id')]

    @property
    def objects(self):
        return QueryManager(self.model)

    @property
    def collection(self):
        return self._collection


class ModelMetaclass(type):
    def __new__(meta, name, bases, attrs):
        """
        For simplicity we disallow multiple inheritance among Models.

        Notice, that a subclass's _meta attribute inherits from its
        bases.  In other words, _meta attributes "stack".

        class Doc_A(Model):
            _meta = {'index': ['name'], 'database': 'test'}
            name = StringField()
            ...

        class Doc_B(Doc_A):
            _meta = {'max_size': 100000}
            ...

        >>> print Doc_B._meta
        {'index': ['name'], 'max_size': 100000, 'database': 'test'}

        Options include:
        index      := [fieldname, ...] (default = [])
        collection := collection name  (default = class name)
        max_size   := integer          (default = 100000 bytes)
        database   := string           (default = '')
        """
        if len(bases) > 1:
            raise InheritanceException(
                'Multiple inheritance not allowed')

        # convert dictproxy to a dict
        base_attrs = dict(bases[0].__dict__)

        _meta = {'index': [], 'collection': name,
                 'max_size': 10000, 'database': ''}

        # pull out meta modifier, then merge with that of current class
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
                return getattr(self, field.name)
        return None

    def to_mongo(self):
        self.validate()
        fields = self._info.fields
        # build a mongo compatible dictionary
        mongo = dict((field.name, field._to_mongo(
                        getattr(self, field.name))) for field in fields)
        return mongo

    @classmethod
    def to_python(cls, mongo):
        pass

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

    def save(self):
        self._info.collection.insert(self.to_mongo())
