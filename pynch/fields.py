from base import Field, Model
from errors import FieldTypeException, DelegationException
from bson.dbref import DBRef
from types import GeneratorType
import pymongo


class DynamicField(Field):
    """
    Marker class for fields that can take data of
    any type. Does no actual validation.
    """
    def _to_mongo(self, data):
        return data

    def _to_python(self, data):
        return data

    def validate(self, data):
        return data


class SimpleField(Field):
    """
    Marker class for fields that can take data of
    any simple type (ie not a container type). Does
    no actual validation.

    TODO: PY3 compatibility for simple types.
    """
    def _to_mongo(self, data):
        return data

    def _to_python(self, data):
        return data

    def validate(self, data):
        return data


class ComplexField(Field):
    """
    Container field type. Can pass in either an instance of a
    field or a reference to an existing model.

    The container elements must all be of the same type, unless
    the underlying field type is dynamic.
    """
    def __init__(self, field=None, **params):
        # ComplexField's cannot be primary keys
        assert not params.pop('primary_key', False), \
                    "ComplexFields may not be primary keys"
        # a reference to the type of each element in the field
        self.field = field if field else DynamicField()
        # all other fields are a go
        super(ComplexField, self).__init__(**params)

    def __call__(self, name, model):
        # if `self.field` is a string (absolute import path) to
        # a model, then rebind the attribute with the correct model.
        if isinstance(self.field, basestring):
            self.field = __import__(self.field)

        # initialize the type of field inside the container
        if isinstance(self.field, SimpleField):
            self.field(name, model)
        if isinstance(self.field, DynamicField):
            self.field(name, Model)
        if isinstance(self.field, ReferenceField):
            self.field(name, self.field.reference)

        return super(ComplexField, self).__call__(name, model)

    def is_dynamic(self):
        return isinstance(self.field, DynamicField)

    def _to_mongo_caller(self, x):
        return x.to_mongo() if \
            issubclass(self.field, Model) else self.field._to_mongo(x)

    def validate(self, data):
        raise DelegationException('Define in a subclass')


class ListField(ComplexField):
    """
    All normal list operations are available. Note that order is preserved.

    class Flower(Model):
        species = StringField(default='Snarling Fly Eater')

        def __str__(self):
            return self.species

    class Garden(Model):
        flowers = ListField(Flower)

    >>> garden = Garden()
    >>> garden.flowers = [Flower(species='Rose'), Flower(species='Daisy')]
    >>> print garden.pop(0)
    Rose
    """
    def __set__(self, document, value):
        if not isinstance(value, list):
            raise FieldTypeException(
                        actually_is=type(value), should_be=list)
        super(ListField, self).__set__(document, value)

    def _to_mongo(self, lst):
        _to_mongo_caller = self._to_mongo_caller  # optimization
        return [_to_mongo_caller(x) for x in lst]

    def _to_python(self, lst):
        _to_python = self.field._to_python        # optimization
        return [_to_python(x) for x in lst]

    def validate(self, lst):
        validate = self.field.validate            # optimization
        return [validate(x) for x in lst]


class DictField(ComplexField):
    """
    Almost identical to a ListField. All normal dict operations
    are available.
    """
    def __set__(self, document, value):
        if not isinstance(value, dict):
            raise FieldTypeException(
                    actually_is=type(value), should_be=dict)
        super(DictField, self).__set__(document, value)

    def _to_mongo(self, dct):
        _to_mongo_caller = self._to_mongo_caller  # optimization
        return dict((k, _to_mongo_caller(v)) for k, v in dct.items())

    def _to_python(self, dct):
        _to_python = self.field._to_python        # optimization
        return dict((k, _to_python(v)) for k, v in dct.items())

    def validate(self, dct):
        validate = self.field.validate            # optimization
        return dict((k, validate(v)) for k, v in dct.items())


class GeneratorField(ComplexField):
    """
    Same as a ListField but with generators instead
    """
    def __set__(self, document, value):
        if not isinstance(value, GeneratorType):
            raise FieldTypeException(
                    actually_is=type(value), should_be=GeneratorType)
        super(GeneratorField, self).__set__(document, value)

    def _to_mongo(self, generator):
        _to_mongo_caller = self._to_mongo_caller  # optimization
        return [_to_mongo_caller(x) for x in generator]

    def _to_python(self, lst):
        _to_python = self.field._to_python        # optimization
        return (_to_python(x) for x in lst)

    def validate(self, lst):
        validate = self.field.validate            # optimization
        return (validate(x) for x in lst)


class ReferenceField(Field):
    """
    class Gardener(Model):
        name = StringField(required=True)
        instructor = ReferenceField('self')

        def __str__(self):
            return self.name

    class BugStomper(Model):
        stomper = ReferenceField(Gardener)
        number_squashed = IntegerField()

    class Garden(Model):
        acres = DecimalField()
        gardener = ReferenceField(Gardener)

    >>> person = Gardener(name='me', instructor=Gardener('MrJones'))
    >>> garden = Garden(acres=0.25, gardener=person)
    >>> print garden.gardener.name
    me
    >>> print person.instructor.name
    MrJones
    >>> print Garden.gardener.reference
    <class Gardener ...>
    >>> print Gardener._info.backrefs
    set([<class Garden ...>, <class Gardener ...>])
    """
    def __init__(self, reference, **params):
        super(ReferenceField, self).__init__(**params)
        self.reference = reference

    def __call__(self, name, model):
        super(ReferenceField, self).__call__(name, model)
        # rebind reference with an actual class if reference is
        # a fully qualified import path (str) or is 'self'
        if isinstance(self.reference, basestring):
            self.reference = self.model if \
                'self' == self.reference else __import__(self.reference)

        # only allow references to documents
        if not issubclass(self.reference, Model):
            # we want to find the class (if is an object), or return `reference`
            actually_is = self.reference if \
                isinstance(self.reference, type) else type(self.reference)
            # raise FieldTypeException for illegal reference type
            raise FieldTypeException(actually_is=actually_is, should_be=Model)

        # collect backrefs in a set
        self.reference._info.backrefs.setdefault(
                        self.name, set()).add(self.model)

        return self

    def __delete__(self, document):
        self.reference._info.backrefs[self.name].remove(self.model)
        super(ReferenceField, self).__delete__(document)

    def _to_python(self, dbref):
        return self.reference(**pymongo.dereference(dbref))

    def _to_mongo(self, document):
        name, host, port = self.reference._meta['database']
        return DBRef(self.reference.__name__, document.pk,
                     database=name, host=host, port=port)

    def validate(self, value):
        if isinstance(value, self.reference):
            return value

        raise FieldTypeException(
                actually_is=type(value), should_be=self.reference)


class StringField(SimpleField):
    def _to_mongo(self, value):
        return super(StringField, self)._to_mongo(unicode(value))

    def _to_python(self, value):
        return unicode(value)

    def validate(self, value):
        if isinstance(value, basestring) or value is None:
            return value

        raise FieldTypeException(
                actually_is=type(value), should_be=basestring)


class IntegerField(SimpleField):
    def _to_mongo(self, value):
        return super(IntegerField, self)._to_mongo(int(value))

    def _to_python(self, value):
        return int(value)

    def validate(self, value):
        if isinstance(value, int) or value is None:
            return value

        raise FieldTypeException(
                actually_is=type(value), should_be=int)


class FloatField(SimpleField):
    def _to_mongo(self, value):
        return super(FloatField, self)._to_mongo(float(value))

    def _to_python(self, value):
        return float(value)

    def validate(self, value):
        if isinstance(value, float) or value is None:
            return value

        raise FieldTypeException(
                actually_is=type(value), should_be=float)


class DecimalField(SimpleField):
    def _to_python(self, value):
        pass

    def _to_mongo(self, value):
        pass


class BooleanField(SimpleField):
    def _to_mongo(self, value):
        return super(BooleanField, self)._to_mongo(bool(value))

    def _to_python(self, value):
        return bool(value)

    def validate(self, value):
        if isinstance(value, bool) or value is None:
            return value

        raise FieldTypeException(
                actually_is=type(value), should_be=bool)


## XXX: Under Construction


class URLField(StringField):
    def validate(self, value):
        # TODO: regex action, url verification
        return super(URLField, self).validate(value)


class EmailField(StringField):
    def validate(self, value):
        # TODO: regex action, email verification
        return super(EmailField, self).validate(value)


class DateTimeField(SimpleField):
    pass


class BinaryField(SimpleField):
    pass


class FileField(SimpleField):
    pass


class ImageField(FileField):
    pass


class GeoPointField(SimpleField):
    pass


class UUIDField(SimpleField):
    pass
