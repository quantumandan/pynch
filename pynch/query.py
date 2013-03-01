class QueryManager(object):
    def __init__(self, model):
        self.model = model

    def find(self, **spec):
        return self.model.to_python(
                    self.model._pynch.collection.find(**spec))

    def find_one(self, **spec):
        for fieldname in spec.keys():
            field = getattr(self.model, fieldname)
            if field.primary_key:
                spec['_id'] = spec.pop(fieldname)
        x = self.model._pynch.collection.find_one(spec)
        if x:
            return self.model.to_python(x)
