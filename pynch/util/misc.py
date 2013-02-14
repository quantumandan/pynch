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


type_of = lambda cls_or_obj: \
                cls_or_obj if isinstance(cls_or_obj, type) else type(cls_or_obj)
