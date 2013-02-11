

class InheritanceException(TypeError):
    pass


class DelegationException(InheritanceException):
    pass


class ValidationException(Exception):
    pass


class DocumentValidationException(ValidationException):
    def __init__(self, msg='Validation Failure', **exceptions):
        self.exceptions = exceptions
        for name, field_exc in exceptions.items():
            msg += '\nField "%s" failed to validate: %s' % (name, field_exc)
        super(DocumentValidationException, self).__init__(msg)
