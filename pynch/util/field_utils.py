from pynch.errors import ValidationException


def field_to_save_tuple(document, field):
    """
    returns tuples with value (field name, mongo value)
    """
    # if field is '_id':
    #     return (field, document._id)
    attr = getattr(document, field.name, None)
    return (field.db_field or field.name, field.to_save(attr))


def get_field_value_or_default(document, field):
    # must convert KeyErrors to AttributeErrors
    try:
        return document.__dict__[field.name]
    except KeyError:
        if field.default is not None:
            return field.default
        raise AttributeError


def field_check_required(document, field):
    if field.required:
        # a required field with a None value is not valid
        # anyway so fail the check if the attribute is
        # either not there or is None
        if getattr(document, field.name, None) is None:
            raise ValidationException('%s is required' % field.name)
        return True


def field_check_choices(document, field):
    if field.choices is None or \
        getattr(document, field.name, None) in field.choices:
        return True

    raise ValidationException(
        '%s is not one of %s' % (field.name, field.choices))


def field_check_unique_with(document, field):
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


def field_check_unique(document, field):
    if field.unique:
        # do check here
        pass
    return True


def check_fields(document):
    """
    Validate the fields, if a failure occurs then yield
    a tuple containing the field name and exception
    """
    # validate the fields' relationships to each other
    for field in document.pynch.fields:
        try:
            field_check_required(document, field)
        except ValidationException as e:
            yield (field.name, e)
        try:
            field_check_choices(document, field)
        except ValidationException as e:
            yield (field.name, e)
        try:
            field_check_unique_with(document, field)
        except ValidationException as e:
            yield (field.name, e)
        try:
            field_check_unique(document, field)
        except ValidationException as e:
            yield (field.name, e)
        try:
            field.validate(getattr(document, field.name, None))
        except ValidationException as e:
            yield (field.name, e)
