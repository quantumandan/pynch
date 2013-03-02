from pynch.errors import FieldTypeException, DelegationException, ValidationException
from pynch.util.misc import import_class
from pynch.base import Field, Model
from bson.dbref import DBRef
from types import GeneratorType
import re


class DynamicField(Field):
    """
    Marker class for fields that can take data of any type.
    Does no actual validation.
    """
    def validate(self, data):
        return data

    def to_save(self, value):
        return value


class SimpleField(Field):
    """
    Marker class for fields that can take data of any simple
    type (ie not a container type). Does no actual validation.

    TODO: PY3 compatibility for simple types.
    """
    BASE_TYPES = (basestring, int, float, bool, long)

    def validate(self, data):
        return data

    def to_save(self, value):
        return value


class ComplexField(Field):
    """
    Container field type. Can pass in an instance of a field,
    else the underlying field type will be dynamic.

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
        # since `set` is normally called by the model's metaclass,
        # when wrapping a DocumentField in a ComplexField it is
        # important so that string references are rebound with the
        # actual classes
        if isinstance(self.field, DocumentField):
            self.field.set(name, self.field.reference)

        super(ComplexField, self).set(name, model)

    def __set__(self, document, value):
        # rebind reference with an actual class
        if isinstance(self.field, DocumentField) and \
            isinstance(self.field.reference, basestring):
            self.field.rebind()
        super(ComplexField, self).__set__(document, value)

    def to_save(self, value):
        return value

    def is_dynamic(self):
        return isinstance(self.field, DynamicField)

    def validate(self, data):
        raise DelegationException('Define in a subclass')

    def _to_python_caller(self, x):
        basetypes = SimpleField.BASE_TYPES
        return x if isinstance(x, basetypes) else self.field.to_python(x)


class ListField(ComplexField):
    """
    All normal list operations are available. Note that order is preserved.
    """
    def __set__(self, document, value):
        if not isinstance(value, list):
            raise FieldTypeException(type(value), list)
        super(ListField, self).__set__(document, value)

    def to_save(self, lst):
        lst = lst if lst else []
        to_save = self.field.to_save             # optimization
        X = [to_save(x) for x in lst]
        return super(ListField, self).to_save(X)

    def to_python(self, lst):
        if lst is not None:
            pc = self._to_python_caller          # optimization
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
        dct = dct if dct else {}
        to_save = self.field.to_save             # optimization
        X = dict((k, to_save(v)) for k, v in dct.items())
        return super(DictField, self).to_save(X)

    def to_python(self, dct):
        if dct is not None:
            pc = self._to_python_caller          # optimization
            return dict((k, pc(v)) for k, v in dct.items())

    def validate(self, dct):
        if dct is not None:
            validate = self.field.validate       # optimization
            return dict((k, validate(v)) for k, v in dct.items())


class SetField(ComplexField):
    def __init__(self, field=None, disjoint_with=None, **modifiers):
        self.disjoint_with = disjoint_with
        super(SetField, self).__init__(**modifiers)

    def __set__(self, document, value):
        if not isinstance(value, set):
            raise FieldTypeException(type(value), set)
        super(SetField, self).__set__(document, value)

    def to_save(self, S):
        S = S if S else set()
        to_save = self.field.to_save             # optimization
        X = [to_save(x) for x in S]
        return super(SetField, self).to_save(X)

    def to_python(self, lst):
        if lst is not None:
            pc = self._to_python_caller          # optimization
            return set(pc(s) for s in lst)

    def validate(self, iterable):
        if iterable is not None:
            validate = self.field.validate       # optimization
            return [validate(s) for s in iterable]


class DocumentField(Field):
    def __init__(self, reference, **params):
        self.reference = reference
        super(DocumentField, self).__init__(**params)

    def set(self, name, model):
        super(DocumentField, self).set(name, model)
        # rebind reference with an actual class (this handles the
        # canonical use case where a valid class, not a string
        # reference, has been passed in to the constructor)
        self.rebind()

    def rebind(self):
        # rebind reference with an actual class if reference is
        # an import path (str) or is 'self', otherwise reference
        # hasn't been read into memory yet, so defer binding
        if isinstance(self.reference, basestring):
            name = self.reference
            self.reference = self.model if 'self' == name else \
                    (import_class(name, self._context) or name)

    def __set__(self, document, value):
        # rebind reference with an actual class (this handles the
        # case that the reference was not in memory during the first
        # attempt at rebinding)
        if isinstance(self.reference, basestring):
            self.rebind()
        # cannot use a subclass or a superclass (types must match)
        if type(value) != self.reference:
            raise ValidationException(
                'Value of type %s must be of type %s, and not a sub/super class' \
                        % (type(value), self.reference))
        super(DocumentField, self).__set__(document, value)


class ReferenceField(DocumentField):
    def rebind(self):
        super(ReferenceField, self).rebind()
        # only add backrefs when the reference has been rebound
        if not isinstance(self.reference, basestring):
            self.reference.pynch.backrefs[self] = self.model

    def to_save(self, document):
        # notice that `ReferenceField.to_save` does not call
        # base class's `to_save`
        if document is not None:
            # need to validate document first to preserve atomicity
            # during cascading saves
            document.validate().save()
            # get all the info needed to point the reference to
            # the correct database
            name, host, port = self.reference._meta['database']
            # turns the document into a DBRef
            return DBRef(self.reference.__name__, document.pk,
                         database=name, host=host, port=port)
        # in this case, document will be None
        return None

    def to_python(self, dbref):
        # if the dbref is not None then delegate to
        # the field's model
        if dbref:
            return self.reference.to_python(
                        self.dereference(dbref) or {})
        # Empty dbref, implies was not set in the db
        return None

    def validate(self, value):
        if value is not None and \
            not isinstance(value, (self.reference, DBRef)):
            raise FieldTypeException(type(value), self.reference)
        return value

    def dereference(self, dbref):
        key = (dbref.host, dbref.port)
        db = self.model.pynch._connection_pool[key][dbref.database]
        return db.dereference(dbref)


class EmbeddedDocumentField(DocumentField):
    def to_save(self, document):
        if document is not None:
            return document.validate().save()
        return None

    def to_python(self, document):
        if document:
            return self.reference.to_python(document)
        return None


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
