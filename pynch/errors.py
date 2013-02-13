class InheritanceException(TypeError):
    pass


class DelegationException(InheritanceException):
    pass


class ValidationException(Exception):
    pass


class FieldTypeException(ValidationException):
    def __init__(self, actually_is=None, should_be=None):
        super(FieldTypeException, self).__init__(
            'value is of type %s but should be %s' % (actually_is, should_be))


class DocumentValidationException(ValidationException):
    def __init__(self, msg='Validation Failure', exceptions=None):
        # since we are clever beasts, notice that an empty dict (as
        # opposed to a MultiDict) will suffice should exceptions be None
        self.exceptions = exceptions if exceptions else {}
        for name, field_exc in self.exceptions.items():
            for exc in field_exc:
                msg += '\nField "%s" failed to validate: %s' % (name, exc)
        super(DocumentValidationException, self).__init__(msg)
