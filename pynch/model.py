from pynch.db import DB
from pynch.errors import InheritanceException, DocumentValidationException
from pynch.util import MultiDict
from pynch.fields import Field, PrimaryKey, check_fields
from pynch.info import InformationDescriptor


class ModelMetaclass(type):
    def __new__(meta, name, bases, attrs):
        if len(bases) > 1:
            raise InheritanceException(
                'Multiple inheritance not allowed')

        # convert mappingproxy to a dict
        try:
            # note that `bases` can be empty and yet produce "new"-style classes
            # ala py2.X ... the curse of new vs old style classes lives on, but
            # now in metaclass land.
            base_attrs = dict(bases[0].__dict__)
        except IndexError:
            base_attrs = dict(object.__dict__)

        # default _meta
        _meta = {'index': [], 'max_size': 10000000, 'database': DB(),
                 'write_concern': 1, 'auto_index': False}

        # pull out _meta modifier, then merge with that of current class
        _meta.update(base_attrs.pop('_meta', {}))
        _meta.update(attrs.pop('_meta', {}))

        # initialize namespace with newly updated _meta
        namespace = {'_meta': _meta}

        # finally update namespace to reflect elements in
        # the new class's __dict__
        namespace.update(base_attrs)
        namespace.update(attrs)

        model = super(ModelMetaclass, meta).__new__(
                            meta, name, bases, namespace)

        # information descriptor allows class level access to
        # orm functionality
        model.pynch = InformationDescriptor(model)

        for fieldname, field in namespace.items():
            if isinstance(field, Field):
                # save a reference to the primary key field on
                # the descriptor
                if field.primary_key or fieldname == '_id':
                    model._id = model.pynch.primary_key_field = field

                # fields named `_id` are automatically indexed by
                # mongo, so skip them
                if fieldname != '_id' and namespace['_meta']['auto_index']:
                    model.pynch.collection.create_index(
                            field.db_field or fieldname, unique=field.unique)

                # Necessary so that field descriptors can determine
                # what classes they are attached to.
                field.set(fieldname, model)

        if model.pynch.primary_key_field is None:
            model._id = PrimaryKey()
            model._id.set('_id', model)
            model.pynch.primary_key_field = model._id
        return model


class Model(metaclass=ModelMetaclass):
    """
    For simplicity we disallow multiple inheritance among Models.

    Notice, that a subclass's _meta attribute inherits from its
    bases.  In other words, _meta attributes "stack".

    Can upcast or downcast types but type enforcement is weak atm
    """
    def __init__(self, *castable, **values):
        super(Model, self).__init__()

        # collect all validation failures
        exceptions = MultiDict()

        for k, v in values.items():
            # setattr must be called to activate the descriptors, rather
            # than update the document's __dict__ directly
            try:
                # if v is None then no acceptable value, for this
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

    def __eq__(self, document):
        """
        This is very expensive for models with many fields or deeply nested
        subdocuments, use accordingly.
        """
        combined = set(self.pynch.fields) | set(document.pynch.fields)
        for field in combined:
            try:
                attr1 = field.get_field_value_or_default(self)
            except AttributeError:
                return False
            try:
                attr2 = field.get_field_value_or_default(document)
            except AttributeError:
                return False
            if attr1 != attr2:
                return False
        return True

    @property
    def pk(self):
        """
        Finds the model's primary key, and sets one if one not already set.
        """
        primary_key_field = self.pynch.primary_key_field
        return self.__dict__.setdefault(primary_key_field.name, self._id)

    @classmethod
    def to_python(cls, mongo):
        python_fields = {}
        for field in cls.pynch.fields:
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

    def to_mongo(self):
        # returns tuples with value (field name, mongo value)
        def field_to_mongo_tuple(field):
            attr = getattr(self, field.name, None)
            return (field.db_field or field.name, field.to_mongo(attr))
        # collect mongo tuples into a dictionary
        mongo = dict(field_to_mongo_tuple(field) \
                                for field in self.pynch.fields)
        return mongo

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

    def save(self, **kwargs):
        # start at the top of the hierarchy and work your way down
        document = self.validate()

        def do_save():
            # loop through the fields creating tuples that can be
            # used to construct a dictionary
            for field in self.pynch.fields:
                # remember that defining a field on a document is
                # not the same as the field value being set
                attr = getattr(self, field.name, None)
                yield (field.db_field or field.name, field.to_save(attr))

        # build a mongo compatible dictionary
        mongo = dict(do_save())

        # save to the database
        self.pynch.collection.save(
                    mongo, w=self._meta['write_concern'], **kwargs)

        return document

    def delete(self):
        oid = self.pk if self.pk else None
        if oid is None:
            raise Exception('Cant delete documents which '
                            'have no _id or primary key')
        self.pynch.collection.remove(oid)
