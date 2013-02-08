from base import BaseField, Model
import re
import decimal


class DynamicField(BaseField):
    """
    Marker class for fields that can take data of any type.
    """
    pass


class ListField(BaseField):
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

    def __init__(self, field=None, **params):
        # get rid of validator if any, we want to hard code one
        params.pop('validator', None)
        # all other parameters are a go
        super(ListField, self).__init__(**params)
        # a reference to the type of each element in the field
        self.field_type = field if field else DynamicField
        # wrap a list comprehension in a lambda fcn
        self.validator = lambda lst: \
            [self.field_type.validator(x) for x in lst]

    def __set__(self, document, value):
        assert isinstance(value, list)
        # remember that `self.validator(...)` returns a list
        # of validated field values, but its the super class's
        # responsibility to call the actual validator and
        # set the resulting list in the document's dictionary
        super(ListField, self).__set__(document, value)

    def _to_mongo(self, document):
        return [self.field_type._to_mongo(document, x) \
                    for x in document.__dict__[self.name]]

    def _to_python(self, document):
        return [self.field_type._to_python(document, x) \
                    for x in document.__dict__[self.name]]

    def is_dynamic(self):
        # is dynamic if contents of the ListField are untyped
        return issubclass(self.field_type, DynamicField)


class DictField(BaseField):
    """
    Almost identical to a ListField. All normal dict operations
    are available.
    """

    def __init__(self, field=None, **params):
        # get rid of validator if any, we want to hard code one
        params.pop('validator', None)
        # all other parameters are a go
        super(DictField, self).__init__(**params)
        # a reference to the type of each element in the field
        self.field_type = field if field else DynamicField
        # wrap a dict comprehension in a lambda fcn
        self.validator = lambda dct: \
            dict((k, self.field_type.validator(v)) for k, v in dct.items())

    def __set__(self, document, value):
        assert isinstance(value, dict)
        # remember that `self.validator(...)` returns a dict
        # of validated field values, but its the super class's
        # responsibility to call the actual validator and
        # set the resulting dict in the document's dictionary
        super(DictField, self).__set__(document, value)

    def _to_mongo(self, document):
        return dict((k, self.field_type._to_mongo(document, v)) \
                    for k, v in document.__dict__[self.name].items())

    def _to_python(self, document):
        return dict((k, self.field_type._to_python(document, v)) \
                    for k, v in document.__dict__[self.name].items())

    def is_dynamic(self):
        # is dynamic if contents of the DictField are untyped
        return issubclass(self.field_type, DynamicField)


class ReferenceField(BaseField):
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

    def __call__(self, name):
        # rebind reference with an actual class if reference is
        # a fully qualified import path (str) or is 'self'
        if isinstance(self.reference, basestring):
            self.reference = self.model if \
                'self' == self.reference else __import__(self.reference)

        # right now, only allow references to documents
        assert isinstance(self.reference, Model)

        # collect backrefs in a set
        self.reference._info.backrefs.setdefault(
                        self.name, set()).add(self.model)

        return super(ReferenceField, self).__call__(name)

    def __delete__(self, document):
        self.reference._info.backrefs[self.name].remove(self.model)
        super(ReferenceField, self).__delete__(document)


class StringField(BaseField):
    pass


class URLField(StringField):
    pass


class EmailField(StringField):
    pass


class IntegerField(BaseField):
    pass


class FloatField(BaseField):
    pass


class DecimalField(BaseField):
    pass


class BooleanField(BaseField):
    pass


class DateTimeField(BaseField):
    pass


class BinaryField(BaseField):
    pass


class FileField(BaseField):
    pass


class ImageField(FileField):
    pass


class GeoPointField(BaseField):
    pass


class SequenceField(IntegerField):
    pass


class UUIDField(BaseField):
    pass
