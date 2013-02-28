class QueryManager(object):
    def __init__(self, model):
        self.model = model

    def find(self, **spec):
        return self.model._pynch.to_python(
                    self.model._pynch.collection.find(**spec))

    def find_one(self, **spec):
        return self.model._pynch.to_python(
                    self.model._pynch.collection.find_one(spec))
