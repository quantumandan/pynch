from pynch.errors import FieldTypeException, DelegationException, ValidationException
from pynch.util.misc import import_class
from pynch.base import Field, Model
from bson.dbref import DBRef
from types import GeneratorType
import re


BASE_TYPES = (basestring, int, float, bool)


class DynamicField(Field):
    """
    Marker class for fields that can take data of any type.
    Does no actual validation.
    """
    def to_save(self, data):
        return data

    def validate(self, data):
        return data


class SimpleField(Field):
    """
    Marker class for fields that can take data of any simple
    type (ie not a container type). Does no actual validation.

    TODO: PY3 compatibility for simple types.
    """
    def to_save(self, data):
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

    def set(self, name, model):
        # initialize the type of field inside the container
        if isinstance(self.field, (SimpleField, DynamicField)):
            self.field.set(name, model)
        if isinstance(self.field, ReferenceField):
            self.field.set(name, self.field.reference)
        super(ComplexField, self).set(name, model)

    def is_dynamic(self):
        return isinstance(self.field, DynamicField)

    def to_mongo_caller(self, x):
        X = self.field.to_save(x)
        return super(ComplexField, self).to_save(X)

    def to_python_caller(self, x):
        return x if isinstance(x, BASE_TYPES) else self.field.to_python(x)

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
        awards = ListField(StringField())
        flowers = ListField(ReferenceField(Flower))

    >>> garden = Garden()
    >>> garden.flowers = [Flower(species='Rose'), Flower(species='Daisy')]
    >>> print garden.pop(0)
    Rose
    """
    def __set__(self, document, value):
        if not isinstance(value, list):
            raise FieldTypeException(type(value), list)
        super(ListField, self).__set__(document, value)

    def to_save(self, lst):
        if lst is None:
            return []
        X = [self.field.to_save(x) for x in lst]
        return super(ListField, self).to_save(X)

    def to_python(self, lst):
        pc = self.to_python_caller               # optimization
        return [pc(x) for x in lst]

    def validate(self, lst):
        if lst is not None:
            validate = self.field.validate       # optimization
            return [validate(x) for x in lst]


class DictField(ComplexField):
    """
    Almost identical to a ListField. All normal dict operations
    are available.
    """
    def __set__(self, document, value):
        if not isinstance(value, dict):
            raise FieldTypeException(type(value), dict)
        super(DictField, self).__set__(document, value)

    def to_save(self, dct):
        if dct is None:
            return {}
        mc = self.to_mongo_caller                # optimization
        return dict((k, mc(v)) for k, v in self.validate(dct).items())

    def to_python(self, dct):
        pc = self.to_python_caller               # optimization
        return dict((k, pc(v)) for k, v in dct.items())

    def validate(self, dct):
        if dct is not None:
            validate = self.field.validate       # optimization
            return dict((k, validate(v)) for k, v in dct.items())


class GeneratorField(ComplexField):
    """
    Same as a ListField but with generators instead.
    """
    def __set__(self, document, value):
        if not isinstance(value, GeneratorType):
            raise FieldTypeException(type(value), GeneratorType)
        super(GeneratorField, self).__set__(document, value)

    def to_save(self, generator):
        if generator is None:
            return []
        mc = self.to_mongo_caller                # optimization
        return [mc(x) for x in self.validate(generator)]

    def to_python(self, lst):
        pc = self.to_python_caller               # optimization
        return (pc(x) for x in lst)

    def validate(self, iterable):
        if iterable is not None:
            validate = self.field.validate       # optimization
            return (validate(x) for x in iterable)


class SetField(ComplexField):
    def __init__(self, field=None, disjoint_with=None, **modifiers):
        self.disjoint_with = disjoint_with
        super(SetField, self).__init__(**modifiers)

    def __set__(self, document, value):
        if not isinstance(value, set):
            raise FieldTypeException(type(value), set)
        super(SetField, self).__set__(document, value)

    def to_save(self, S):
        if S is None:
            return []
        X = [self.field.to_save(x) for x in S]
        return super(SetField, self).to_save(X)

    def to_python(self, lst):
        pc = self.to_python_caller               # optimization
        return set(pc(s) for s in lst)

    def validate(self, iterable):
        if iterable is not None:
            validate = self.field.validate       # optimization
            return set(validate(s) for s in iterable)


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
    >>> print Gardener._pynch.backrefs
    set([<class 'Garden' ...>, <class 'Gardener' ...>])
    """
    def __init__(self, reference, **params):
        self.reference = reference
        super(ReferenceField, self).__init__(**params)

    def set(self, name, model):
        super(ReferenceField, self).set(name, model)
        # rebind reference with an actual class if reference is
        # an import path (str) or is 'self', otherwise reference
        # hasn't been read into memory yet, so defer binding
        if isinstance(self.reference, basestring):
            model_name = self.reference
            self.reference = \
                self.model if 'self' == model_name else \
                    (import_class(model_name, self._context) or model_name)

        #  if reference is a basestring then the referent has not been set
        if not isinstance(self.reference, basestring):
            # only allow references to documents
            if not issubclass(self.reference, Model):
                raise FieldTypeException(self.reference, Model)
            # only add backrefs when the reference has been rebound
            self.reference._pynch.backrefs.setdefault(
                            self.name, set()).add(self.model)

    def __get__(self, document, model=None):
        # does lazy rebinding of references in the event that
        # the deed has not already been done
        if issubclass(self.model, basestring):
            self.set(self.name, model)
        # get the value from the document's dictionary
        return super(ReferenceField, self).__get__(document, model)

    def __delete__(self, document):
        self.reference._pynch.backrefs[self.name].remove(self.model)
        super(ReferenceField, self).__delete__(document)

    def to_save(self, document):
        mongo_doc = super(ReferenceField, self).to_save(document)
        if mongo_doc is not None:
            name, host, port = self.reference._meta['database']
            # turns the document into a DBRef
            return DBRef(self.reference.__name__, mongo_doc.pk,
                         database=name, host=host, port=port)
        # in this case, document will be None
        return mongo_doc

    def to_python(self, dbref):
        # fails silently, not optimal
        R = self.dereference(dbref) or {}
        return self.reference(**R)

    def validate(self, value):
        if not isinstance(value, (self.reference, DBRef)) \
                and value is not None:
            raise FieldTypeException(type(value), self.reference)
        return value

    def dereference(self, dbref):
        key = (dbref.host, dbref.port)
        db = self.model._pynch._connection_pool[key][dbref.database]
        return db.dereference(dbref)


class StringField(SimpleField):
    def __init__(self, max_length=None, **params):
        self.max_length = max_length
        super(StringField, self).__init__(**params)

    def to_save(self, value):
        value = unicode(value) if value is not None else value
        return super(StringField, self).to_save(value)

    def to_python(self, value):
        return unicode(value)

    def validate(self, value):
        if not isinstance(value, basestring) and value is not None:
            raise FieldTypeException(type(value), basestring)

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

    def to_save(self, value):
        value = int(value) if value is not None else value
        return super(IntegerField, self).to_save(value)

    def to_python(self, value):
        return int(value)

    def validate(self, value):
        if not isinstance(value, int) and value is not None:
            raise FieldTypeException(type(value), int)

        if value is not None:
            if self.min_value and value < self.min_value:
                raise ValidationException(
                    '%s is less than the minimum allowed value' % self.name)

            if self.max_value and value > self.max_value:
                raise ValidationException(
                    '%s is greater than the maximum allowed value' % self.name)

        return value


class FloatField(SimpleField):
    def __init__(self, min_value=None, max_value=None, **params):
        self.min_value = min_value
        self.max_value = max_value
        super(FloatField, self).__init__(**params)

    def to_save(self, value):
        value = float(value) if value is not None else value
        return super(FloatField, self).to_save(value)

    def to_python(self, value):
        return float(value)

    def validate(self, value):
        if not isinstance(value, float) and value is not None:
            raise FieldTypeException(type(value), float)

        if value is not None:
            if self.min_value and value < self.min_value:
                raise ValidationException(
                    '%s is less than the minimum allowed value' % self.name)

            if self.max_value and value > self.max_value:
                raise ValidationException(
                    '%s is greater than the maximum allowed value' % self.name)

        return value


class BooleanField(SimpleField):
    def to_save(self, value):
        value = bool(value) if value is not None else value
        return super(BooleanField, self).to_save(value)

    def to_python(self, value):
        return bool(value)

    def validate(self, value):
        if not isinstance(value, bool) and value is not None:
            raise FieldTypeException(type(value), bool)
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
    def to_save(self, value):
        pass

    def to_python(self, value):
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
