from errors import ValidationException


def field_check_required(document, field):
    if field.required:
        # a field with a None value is not valid
        # anyway so fail the check if the attribute
        # is either not there or is None
        if getattr(document, field.name, None) is None:
            raise ValidationException('field %s is required' % field.name)
        return True


def field_check_unique(document, field):
    if field.unique:
        # do check here
        pass
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
            raise ValidationException('field %s is not unique with field %s' \
                    % (field.name, unique_field_name))


def field_master_check(document, field):
    # delegate validation to the document's fields
    field.validate(getattr(document, field.name, None))
    field_check_required(document, field)
    field_check_unique(document, field)
    field_check_unique_with(document, field)
