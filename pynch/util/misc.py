class MultiDict(dict):
    """
    Poor man's multidict. Works like a normal dictionary in
    every respect except when the constructor is called with
    an iterable of tuples. Then, multiple elements with the
    same key are aggregated into a list.
    """
    def __init__(self, *args, **kwargs):
        dict.__init__(self, **kwargs)
        if len(args) == 1:
            for key, value in args[0]:
                self.setdefault(key, []).append(value)


UnboundReference = type('UnboundReference', (), {})


def import_class(to_import, context=''):
    # if `.` not in the import path then we are referencing
    # a class relative to the module to which it belongs
    # such things occur when running a module as a script,
    # in which case context would be `__main__`
    if '.' not in to_import:
        module, clsname = context, to_import
    else:
        d, n = to_import.rfind('.'), len(to_import)
        module, clsname = to_import[0:d], to_import[d+1:n]

    # same as `from module import clsname`
    m = __import__(module, [clsname])
    # returns None when the class doesn't exist in the module's
    # namespace, either because the class hasn't been loaded
    # yet, or the class doesn't exist
    return getattr(m, clsname, None)


type_of = lambda cls_or_obj: \
    cls_or_obj if isinstance(cls_or_obj, type) else type(cls_or_obj)


def raise_(exc):
    """
    Functional version of `raise`
    """
    raise exc


def dir_(thing):
    from_name_tuple = lambda name: (name, getattr(thing, name))
    return dict(from_name_tuple(name) for name in dir(thing))
