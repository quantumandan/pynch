def check_required(document, field):
    if field.required:
        # a field with a None value is not valid
        # anyway so fail the check if the attribute
        # is either not there or is None
        if getattr(document, field.name, None):
            return False
    return True


def check_unique(document, field):
    if field.unique:
        # do check here
        pass
    return True


def check_unique_with(document, field):
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
            return False


def document_master_check(document):
    for field in document._info.fields:
        if not check_required(document, field):
            return False
        if not check_unique(document, field):
            return False
        if not check_unique_with(document, field):
            return False
    return True
