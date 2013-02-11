from base import Field, Model
from bson.dbref import DBRef
import types
import collections


class DynamicField(Field):
    """
    Marker class for fields that can take data of any type.
    Does no validation.
    """
    def _to_mongo(self, data):
        return data

    def _to_python(self, data):
        return data

    def validate(self, data):
        return data


class ComplexField(Field):
    """
    Container type field. Can pass in either a instance of a
    field or a reference to an existing model.

    Container elements must all be of the same type.
    """
    def __init__(self, field=None, **params):
        super(ComplexField, self).__init__(**params)
        # a reference to the type of each element in the field
        self.field = field if field else DynamicField()

    def __call__(self, name, model):
        if isinstance(self.field, ReferenceField):
            self.field(name, self.field.reference)
        if isinstance(self.field, DynamicField):
            self.field(name, Model)
        return super(ComplexField, self).__call__(name, model)

    def is_dynamic(self):
        # is dynamic if contents of the DictField are untyped
        return isinstance(self.field, DynamicField)


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
        assert isinstance(value, list)
        super(ListField, self).__set__(document, value)

    def _to_mongo(self, document):
        return [self.field._to_mongo(x) \
                    for x in document.__dict__[self.name]]

    def _to_python(self, document):
        return [self.field._to_python(x) \
                    for x in document.__dict__[self.name]]

    def validate(self, lst):
        return [self.field.validate(x) for x in lst]


class DictField(ComplexField):
    """
    Almost identical to a ListField. All normal dict operations
    are available.
    """
    def __set__(self, document, value):
        assert isinstance(value, dict)
        super(DictField, self).__set__(document, value)

    def _to_mongo(self, document):
        return dict((k, self.field._to_mongo(v)) \
                    for k, v in document.__dict__[self.name].items())

    def _to_python(self, document):
        return dict((k, self.field._to_python(v)) \
                    for k, v in document.__dict__[self.name].items())

    def validate(self, dct):
        return dict((k, self.field.validate(v)) for k, v in dct.items())


class GeneratorField(ComplexField):
    """
    Same as a ListField but with generators instead
    """
    def __set__(self, document, value):
        assert isinstance(value, (types.GeneratorType, collections.Iterator))
        super(GeneratorField, self).__set__(document, value)

    def _to_mongo(self, document):
        return [self.field._to_mongo(x) \
                    for x in document.__dict__[self.name]]

    def _to_python(self, document):
        return (self.field._to_python(x) \
                    for x in document.__dict__[self.name])

    def validate(self, gen):
        return (self.field.validate(x) for x in gen)


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
    >>> print Gardener.gardener.reference
    <class Gardener ...>
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
        assert issubclass(self.reference, Model)

        # collect backrefs in a set
        self.reference._info.backrefs.setdefault(
                        self.name, set()).add(self.model)

        return self

    def __delete__(self, document):
        self.reference._info.backrefs[self.name].remove(self.model)
        super(ReferenceField, self).__delete__(document)

    def _to_python(self, mongo):
        pass

    def _to_mongo(self, document):
        return DBRef(self.reference.__name__, document.db_field,
                     database=self.reference._meta.database)

    def validate(self, data):
        assert isinstance(data, self.reference)
        return data


class StringField(Field):
    def validate(self, value):
        assert isinstance(value, basestring)
        return value

    def _to_mongo(self, value):
        return unicode(value)

    _to_python = _to_mongo


class URLField(StringField):
    pass


class EmailField(StringField):
    pass


class IntegerField(Field):
    def validate(self, value):
        assert isinstance(value, int)
        return value

    def _to_mongo(self, value):
        return int(value)

    _to_python = _to_mongo


class FloatField(Field):
    def validate(self, value):
        assert isinstance(value, float)
        return value

    def _to_mongo(self, value):
        return float(value)

    _to_python = _to_mongo


class DecimalField(Field):
    def _to_python(self, value):
        pass

    def _to_mongo(self, value):
        pass


class BooleanField(Field):
    def validate(self, value):
        assert isinstance(value, bool)
        return value

    def _to_mongo(self, value):
        return bool(value)

    _to_python = _to_mongo


class DateTimeField(Field):
    pass


class BinaryField(Field):
    pass


class FileField(Field):
    pass


class ImageField(FileField):
    pass


class GeoPointField(Field):
    pass


class UUIDField(Field):
    pass
