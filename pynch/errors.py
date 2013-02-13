class InheritanceException(TypeError):
    pass


class DelegationException(InheritanceException):
    pass


class ValidationException(Exception):
    pass


class ValidationTypeException(ValidationException):
    def __init__(self, actually_is=None, should_be=None):
        super(ValidationException, self).__init__(
            'value is of type %s but should be %s' % (actually_is, should_be))


class DocumentValidationException(ValidationException):
    def __init__(self, msg='Validation Failure', exceptions=None):
        exceptions = exceptions if exceptions else {}
        for name, field_exc in exceptions.items():
            for exc in field_exc:
                msg += '\nField "%s" failed to validate: %s' % (name, exc)
        super(DocumentValidationException, self).__init__(msg)
