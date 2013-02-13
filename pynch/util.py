from errors import ValidationException


class MultiDict(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, **kwargs)
        if len(args) == 1:
            for key, value in args[0]:
                self.setdefault(key, []).append(value)


def field_check_required(document, field):
    if field.required:
        # a field with a None value is not valid
        # anyway so fail the check if the attribute
        # is either not there or is None
        if getattr(document, field.name, None) is None:
            raise ValidationException('%s is required' % field.name)
        return True


def field_check_unique_with(document, field):
    # just because a model declares a field doesn't mean
    # the corresponding document will have that attribute
    unique_value = getattr(document, field.name, None)
    # if the unique_value is None then the attribute hasn't
    # been set on the document so there is nothing to check
    if not unique_value:
        return True

    unique_with = field.unique_with

    for unique_field_name in unique_with:
        # just because a model declares a field doesn't mean
        # the corresponding document will have that attribute
        document_value = getattr(document, unique_field_name, None)
        # if the document_value is None then the attribute hasn't
        # been set on the document
        if document_value is None:
            continue

        if document_value == unique_value:
            raise ValidationException('%s is not unique with field %s' \
                    % (field.name, unique_field_name))


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
    for field in document._info.fields:
        # validate the fields' relationships to each other, then
        # delegate validation of the actual instance data to the
        # document's fields
        try:
            field_check_required(document, field)
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
