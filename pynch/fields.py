from pynch.base import Field, Model
from pynch.util.misc import type_of, import_class
from pynch.errors import FieldTypeException, DelegationException, ValidationException
from bson.dbref import DBRef
from types import GeneratorType
import pymongo
import re


class DynamicField(Field):
    """
    Marker class for fields that can take data of any type.
    Does no actual validation.
    """
    def _to_python(self, data):
        return data

    def validate(self, data):
        return data


class SimpleField(Field):
    """
    Marker class for fields that can take data of any simple
    type (ie not a container type). Does no actual validation.

    TODO: PY3 compatibility for simple types.
    """
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
            self.field = import_class(self.field, self._context)

        # initialize the type of field inside the container
        if isinstance(self.field, (SimpleField, DynamicField)):
            self.field(name, model)
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
                    actually_is=type_of(value), should_be=list)

        super(ListField, self).__set__(document, value)

    def _to_mongo(self, lst):
        mc = self._to_mongo_caller                # optimization
        return [mc(x) for x in self.validate(lst)]

    def _to_python(self, lst):
        tp = self.field._to_python                # optimization
        return [tp(x) for x in lst]

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
                    actually_is=type_of(value), should_be=dict)

        super(DictField, self).__set__(document, value)

    def _to_mongo(self, dct):
        mc = self._to_mongo_caller                # optimization
        return dict((k, mc(v)) for k, v in self.validate(dct).items())

    def _to_python(self, dct):
        tp = self.field._to_python                # optimization
        return dict((k, tp(v)) for k, v in dct.items())

    def validate(self, dct):
        validate = self.field.validate            # optimization
        return dict((k, validate(v)) for k, v in dct.items())


class GeneratorField(ComplexField):
    """
    Same as a ListField but with generators instead.
    """
    def __set__(self, document, value):
        if not isinstance(value, GeneratorType):
            raise FieldTypeException(
                    actually_is=type_of(value), should_be=GeneratorType)

        super(GeneratorField, self).__set__(document, value)

    def _to_mongo(self, generator):
        mc = self._to_mongo_caller                # optimization
        return [mc(x) for x in self.validate(generator)]

    def _to_python(self, lst):
        tp = self.field._to_python                # optimization
        return (tp(x) for x in lst)

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
        gardeners = ListField(ReferenceField(Gardener))

    >>> person = Gardener(name='me', instructor=Gardener('MrJones'))
    >>> garden = Garden(acres=0.25, gardeners=[person])
    >>> print garden.gardeners
    ['me']
    >>> print person.instructor.name
    'MrJones'
    >>> print Garden.gardener.reference
    <class 'Gardener' ...>
    >>> print Gardener._info.backrefs
    set([<class 'Garden' ...>, <class 'Gardener' ...>])
    """
    def __init__(self, reference, **params):
        self.reference = reference
        super(ReferenceField, self).__init__(**params)

    def __call__(self, name, model):
        super(ReferenceField, self).__call__(name, model)
        # rebind reference with an actual class if reference is
        # a fully qualified import path (str) or is 'self'
        if isinstance(self.reference, basestring):
            self.reference = self.model if \
                'self' == self.reference else \
                    import_class(self.reference, context=self._context)

        # only allow references to documents
        if not issubclass(self.reference, Model):
            raise FieldTypeException(
                    actually_is=type_of(self.reference), should_be=Model)

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
        self.validate(document)
        name, host, port = self.reference._meta['database']
        return DBRef(self.reference.__name__, document.pk,
                     database=name, host=host, port=port)

    def validate(self, value):
        if not isinstance(value, self.reference):
            raise FieldTypeException(
                    actually_is=type_of(value), should_be=self.reference)
        return value


class StringField(SimpleField):
    def __init__(self, max_length=None, **params):
        self.max_length = max_length
        super(StringField, self).__init__(**params)

    def _to_mongo(self, value):
        value = unicode(value) if value is not None else value
        return super(StringField, self)._to_mongo(value)

    def _to_python(self, value):
        return unicode(value)

    def validate(self, value):
        if not isinstance(value, basestring) and value is not None:
            raise FieldTypeException(
                    actually_is=type_of(value), should_be=basestring)

        exceeds_length = len(value) > self.max_length \
                                if self.max_length else False

        if exceeds_length:
            raise ValidationException(
                '%s exceeds the maximum number of characters' % self.name)

        return value


class IntegerField(SimpleField):
    def __init__(self, min_value=None, max_value=None, **params):
        self.min_value = min_value
        self.max_value = max_value
        super(IntegerField, self).__init__(**params)

    def _to_mongo(self, value):
        value = int(value) if value is not None else value
        return super(IntegerField, self)._to_mongo(value)

    def _to_python(self, value):
        return int(value)

    def validate(self, value):
        if not isinstance(value, int) and value is not None:
            raise FieldTypeException(
                    actually_is=type_of(value), should_be=int)

        if value is not None:
            if self.min_value and value < self.min_value:
                raise ValidationException(
                    '%s less than the minimum allowed value' % self.name)

            if self.max_value and value > self.max_value:
                raise ValidationException(
                    '%s greater than the maximum allowed value' % self.name)

        return value


class FloatField(SimpleField):
    def __init__(self, min_value=None, max_value=None, **params):
        self.min_value = min_value
        self.max_value = max_value
        super(FloatField, self).__init__(**params)

    def _to_mongo(self, value):
        value = float(value) if value is not None else value
        return super(FloatField, self)._to_mongo(value)

    def _to_python(self, value):
        return float(value)

    def validate(self, value):
        if not isinstance(value, float) and value is not None:
            raise FieldTypeException(
                    actually_is=type_of(value), should_be=float)

        if value is not None:
            if self.min_value and value < self.min_value:
                raise ValidationException(
                    '%s lesser than the minimum allowed value' % self.name)

            if self.max_value and value > self.max_value:
                raise ValidationException(
                    '%s greater than the maximum allowed value' % self.name)

        return value


class BooleanField(SimpleField):
    def _to_mongo(self, value):
        value = bool(value) if value is not None else value
        return super(BooleanField, self)._to_mongo(value)

    def _to_python(self, value):
        return bool(value)

    def validate(self, value):
        if not isinstance(value, bool) and value is not None:
            raise FieldTypeException(
                    actually_is=type_of(value), should_be=bool)
        return value


email_regex = \
    re.compile(r'^[_A-Za-z0-9-]+(\\.[_A-Za-z0-9-]+)*@[A-Za-z0-9]+(\\.[A-Za-z0-9]+)*(\\.[A-Za-z]{2,})$')


class EmailField(StringField):
    def validate(self, value):
        if email_regex.match(value):
            return super(EmailField, self).validate(value)
        raise ValidationException('Invalid email address')


## XXX: Under Construction


class URLField(StringField):
    # TODO: regex action, url verification
    def validate(self, value):
        return super(URLField, self).validate(value)


class DecimalField(SimpleField):
    def _to_python(self, value):
        pass

    def _to_mongo(self, value):
        pass

    def validate(self, value):
        pass


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
