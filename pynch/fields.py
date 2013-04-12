from pynch.errors import *
from bson.dbref import DBRef
import re
import inspect
from pynch.util import import_class
from bson.objectid import ObjectId


class Field(object):
    BASE_TYPES = (basestring, int, float, bool, long)

    def __new__(cls, *args, **modifiers):
        """
        Necessary so that reference fields can import and
        bind the correct classes when their models' reside
        in a module being run as a script (ie in the unittests)
        """
        field = super(Field, cls).__new__(cls)
        frame = inspect.stack()[-1][0]  # outermost frame
        field._context = frame.f_locals.get('__name__', '')
        del frame
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
        self.unique = unique if unique else primary_key
        # since unique_with can be either a string or a list
        # of strings, we must check and convert as needed
        self.unique_with = unique_with if unique_with else []
        self.choices = choices
        self.help_text = help_text

    def set(self, name, model):
        """
        Normally called by a model's metaclass at the time fields are
        being attached.  In subclasses, takes care of rebinding references.
        """
        self.name = name
        self.model = model

    def is_set(self):
        return hasattr(self, 'name') and hasattr(self, 'model')

    def is_dynamic(self):
        return isinstance(self.field, DynamicField)

    def get_field_value_or_default(self, document):
        # must convert KeyErrors to AttributeErrors
        try:
            return document.__dict__[self.name]
        except KeyError:
            if self.default is not None:
                return self.default
            raise AttributeError

    def __get__(self, document, model=None):
        # return field instance if accessed through the class
        if document is None:
            return self
        # converts KeyErrors to AttributeErrors in the event
        # that the value is not found in the document and the
        # default is None
        return self.get_field_value_or_default(document)

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
    To use, define a getter and a setter, and any additional
    attributes you'd like the proxy to have. An example of
    how you could make a fake pk is:

    class PK(FieldProxy):
    def __init__(self, **kwargs):
        kwargs['primary_key'] = True
        kwargs['unique'] = True

        # define getters and setters
        def get_ID(doc):
            return doc.__dict__.setdefault('_id', ObjectId())

        def set_ID(doc, value):
            doc.__dict__['_id'] = value

        super(PK, self).__init__(get_ID, set_ID, **kwargs)
    """
    def __init__(self, fget=None, fset=None,
                 fdel=None, doc=None, field=None, **kwargs):
        property.__init__(self, fget, fset, fdel, doc)
        self.__dict__['_field'] = field if \
            isinstance(field, Field) else SimpleField(**kwargs)

    def __getattr__(self, key, default=None):
        return getattr(self._field, key, default)

    def set(self, name, model):
        self._field.set(name, model)

    def to_python(self, value):
        return self._field.to_python(value)

    def validate(self, value):
        return self._field.validate(value)

    def to_save(self, value):
        return self._field.to_save(value)


class DynamicField(Field):
    """
    Marker class for fields that can take data of any type.
    Does no actual validation.
    """
    # here for List/DictField support
    def __getitem__(self, key):
        return self

    def validate(self, data):
        return data

    def to_save(self, value):
        return value

    def to_python(self, value):
        return value

    to_mongo = to_save


class SimpleField(Field):
    """
    Marker class for fields that can take data of any simple
    type (ie not a container type). Does no actual validation.

    TODO: PY3 compatibility for simple types.
    """
    def validate(self, data):
        return data

    def to_save(self, value):
        return value

    def to_python(self, value):
        return value

    to_mongo = to_save


class ComplexField(Field):
    """
    Container field type. Can pass in an instance of a field,
    else the underlying field type will be dynamic.

    The container elements must all be of the same type, unless
    the underlying field type is dynamic.
    """
    def __init__(self, field=None, **params):
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
        # important to manually call `set` so that string references
        # are rebound with the actual classes
        if isinstance(self.field, DocumentField):
            self.field.set(name, self.field.reference)

        super(ComplexField, self).set(name, model)

    def __set__(self, document, value):
        # rebind reference with an actual class
        if isinstance(self.field, DocumentField) and \
            isinstance(self.field.reference, basestring):
            self.field.rebind()
            # if rebinding hasn't succeeded by this point then the
            # reference is invalid
            if isinstance(self.field.reference, basestring):
                raise ValidationException('Failed to rebind references')
        super(ComplexField, self).__set__(document, value)

    def to_save(self, value):
        return value

    to_mongo = to_save

    def validate(self, data):
        raise DelegationException('Define in a subclass')

    def _to_python_caller(self, x):
        basetypes = Field.BASE_TYPES
        return x if isinstance(x, basetypes) else self.field.to_python(x)


class DocumentField(Field):
    def __init__(self, reference, **params):
        self.reference = reference
        super(DocumentField, self).__init__(**params)

    def set(self, name, model):
        super(DocumentField, self).set(name, model)
        self.rebind()

    def rebind(self):
        # rebind reference with an actual class if reference is an
        # import path (str) or is 'self', otherwise reference hasn't
        # been read into memory yet, so defer binding until the first
        # time we try and set a value on the field's document
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
            # if rebinding hasn't succeeded by this point then the
            # reference is invalid
            if isinstance(self.reference, basestring):
                raise ValidationException('Failed to rebind references')
        # cannot use a subclass or a superclass (types must match)
        if type(value) != self.reference:
            raise ValidationException(
                'Value of type %s must be exactly of type %s' \
                        % (type(value), self.reference))
        super(DocumentField, self).__set__(document, value)

    def validate(self, value):
        if value is not None and \
            not isinstance(value, self.reference):
            raise FieldTypeException(type(value), self.reference)
        return value


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

    to_mongo = to_save


class DictField(ComplexField):
    """
    Almost identical to a ListField. All normal dict operations
    are available. Unlike other ComplexFields, a DictField can
    be marked as a primary key, to be used as compound pk's.

    class DynamicDictModel(Model):
        things = DictField()

    names = {'first_name': StringField(),
             'last_name': StringField()}

    class TypedDictModel(Model):
        fullname = DictField(names)

    """
    def set(self, name, model):
        for subfieldname, subfield in self.field.items():
            subfield.set(subfieldname, model)
        super(DictField, self).set(name, model)

    def __set__(self, document, value):
        if not isinstance(value, dict):
            raise FieldTypeException(type(value), dict)
        super(DictField, self).__set__(document, value)

    def to_save(self, dct):
        dct = dct if dct else {}
        X = dict((k, self.field[k].to_save(v)) for k, v in dct.items())
        return super(DictField, self).to_save(X)

    def to_python(self, dct):
        if dct is not None:
            pc = self._to_python_caller          # optimization
            return dict((k, pc(k, v)) for k, v in dct.items())

    def validate(self, dct):
        if dct is not None:
            return dict((k, self.field[k].validate(v)) for k, v in dct.items())

    def _to_python_caller(self, k, x):
        basetypes = SimpleField.BASE_TYPES
        return x if isinstance(x, basetypes) else self.field[k].to_python(x)

    to_mongo = to_save


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

    to_mongo = to_save


class ReferenceField(DocumentField):
    def rebind(self):
        super(ReferenceField, self).rebind()
        # only add backrefs when the reference has been rebound
        if not isinstance(self.reference, basestring):
            self.reference.pynch.backrefs[self] = self.model

    def to_mongo(self, document):
        # notice that `ReferenceField.to_save` does not call
        # base class's `to_mongo`
        if document is not None:
            # get all the info needed to point the reference to
            # the correct database
            name, host, port = self.reference._meta['database']
            # turns the document into a DBRef
            return DBRef(self.reference.__name__, document.pk,
                         database=name, host=host, port=port)
        # in this case, document will be None
        return None

    def to_save(self, document):
        if document is not None:
            document.save()
            return self.to_mongo(document)
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

    def dereference(self, dbref):
        key = (dbref.host, dbref.port)
        db = self.model.pynch._connection_pool[key][dbref.database]
        return db.dereference(dbref)


class EmbeddedDocumentField(DocumentField):
    def to_save(self, document):
        if document is not None:
            return document.to_mongo()
        return None

    to_mongo = to_save

    def to_python(self, document):
        if document is not None:
            return self.reference.to_python(document)
        return None

    def validate(self, value):
        return value.validate()


class PrimaryKey(SimpleField):
    def __init__(self, **kwargs):
        kwargs['primary_key'] = True
        kwargs['unique'] = True
        super(PrimaryKey, self).__init__(**kwargs)

    def __get__(self, document, model=None):
        if document is None:
            return self
        return document.__dict__.setdefault('_id', ObjectId())


class ComplexPrimaryKey(DictField):
    def __init__(self, **kwargs):
        kwargs['primary_key'] = True
        kwargs['unique'] = True
        kwargs['required'] = True
        super(PrimaryKey, self).__init__(**kwargs)

    def set(self, name, model):
        """
        Automatically sets the field's `required` parameter to True
        as it defeats the purpose of a compund or composite key that
        is missing parts
        """
        for field in model.pynch.fields:
            field.required = True
        super(ComplexPrimaryKey, self).set(name, model)


class StringField(SimpleField):
    def __init__(self, max_length=None, **params):
        self.max_length = max_length
        super(StringField, self).__init__(**params)

    def to_save(self, value):
        if value is not None:
            value = unicode(value)
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

    to_mongo = to_save


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

    to_mongo = to_save


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

    to_mongo = to_save


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

    to_mongo = to_save


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


def check_required(field, document):
    if field.required:
        # a required field with a None value is not valid
        # anyway so fail the check if the attribute is
        # either not there or is None
        if getattr(document, field.name, None) is None:
            raise ValidationException('%s is required' % field.name)
        return True


def check_choices(field, document):
    if field.choices is None or \
        getattr(document, field.name, None) in field.choices:
        return True
    raise ValidationException(
        '%s is not one of %s' % (field.name, field.choices))


def check_unique_with(field, document):
    # just because a model declares a field doesn't mean
    # the corresponding document will have that attribute
    unique_value = getattr(document, field.name, None)

    # if the unique_value is None then the attribute hasn't
    # been set on the document so there is nothing to check
    if unique_value is None:
        return True

    unique_with = field.unique_with

    # since unique_with can be either a string or a list
    # of strings, we must check and convert as needed
    unique_with = unique_with if \
            isinstance(unique_with, list) else [unique_with]

    for unique_field_name in unique_with:
        # just because a model declares a field doesn't mean
        # the corresponding document will have that attribute
        document_value = getattr(document, unique_field_name, None)

        # if the document_value is None then the attribute hasn't
        # been set on the document
        if document_value is None:
            continue

        if document_value == unique_value:
            raise ValidationException(
                '%s is not unique with field %s' % \
                        (field.name, unique_field_name))
    return True


def check_fields(document):
    """
    Validate the fields, if a failure occurs then yield
    a tuple containing the field name and exception
    """
    # validate the fields' relationships to each other
    for field in document.pynch.fields:
        try:
            check_required(field, document)
        except ValidationException as e:
            yield (field.name, e)
        try:
            check_choices(field, document)
        except ValidationException as e:
            yield (field.name, e)
        try:
            check_unique_with(field, document)
        except ValidationException as e:
            yield (field.name, e)
        try:
            value = getattr(document, field.name, None)
            field.validate(value)
        except ValidationException as e:
            yield (field.name, e)
