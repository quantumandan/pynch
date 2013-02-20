from pymongo.errors import ConnectionFailure


class InheritanceException(TypeError):
    pass


class DelegationException(InheritanceException):
    pass


class ConnectionException(ConnectionFailure):
    pass


class ValidationException(ValueError):
    pass


class FieldTypeException(ValidationException):
    def __init__(self, actually_is=None, should_be=None, *msg):
        # discard msg
        super(FieldTypeException, self).__init__(
            'value is of type %s but should be a (sub)type of %s' \
                % (actually_is, should_be))


class DocumentValidationException(ValidationException):
    def __init__(self, msg='Validation Failure', exceptions=None):
        # since we are clever beasts, notice that an empty dict (as
        # opposed to a MultiDict) will suffice should exceptions be None
        self.exceptions = exceptions if exceptions else {}
        for name, field_exceptions in self.exceptions.items():
            # wrap field_exceptions in a list in case we want to pass an
            # ordinary dictionary, as opposed to a MultiDict, into the exception
            field_exceptions = field_exceptions if \
                isinstance(field_exceptions, list) else [field_exceptions]
            # collect err msgs
            for exc in field_exceptions:
                msg += '\nField "%s" failed to validate: %s' % (name, exc)

        super(DocumentValidationException, self).__init__(msg)
