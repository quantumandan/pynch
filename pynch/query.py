class QueryManager(object):
    def __init__(self, model):
        self.model = model

    def __call__(self, **kwargs):
        return self.model.pynch.find(kwargs)
