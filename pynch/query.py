from bson.objectid import ObjectId


class QueryManager(object):
    def __init__(self, document_class):
        self.model = document_class

    def update(self, spec, **kwargs):
        self.model._info.collection.update(spec, self.to_mongo(), **kwargs)

    def insert(self, *args, **kwargs):
        self.model._info.collection.insert(self.to_mongo(), **kwargs)

    def save(self, **kwargs):
        self.model._info.collection.save(self.to_mongo(), **kwargs)

    def delete(self):
        oid = ObjectId(self.pk) if self.pk else None
        if oid is None:
            raise Exception('Cant delete documents which '
                            'have no _id or primary key')
        self.model._info.collection.remove(oid)

    def find(self, **spec):
        return self.model.to_python(self.model._info.collection.find(**spec))

    def find_one(self, **spec):
        return self.model.to_python(self.model._info.collection.find_one(spec))


class Query(object):
    pass
