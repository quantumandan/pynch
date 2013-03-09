class QueryManager(object):
    def __init__(self, model):
        self.model = model

    def __call__(self, **kwargs):
        return self.model.pynch.find(kwargs)


def search(obj, search_term, query_filter=None):
    """
    TODO: implement results filtering

    class Petal(Model):
        color = StringField()
    class Flower(Model):
        petals = ListField(ReferenceField(Petal))
    class Garden(Model):
        flowers = ListField(ReferenceField(Flowers))
    ...
    # returns a generator with the colors of all the
    # red or blue hued petals, of all the flowers in
    # the garden.
    hue = Q('flowers.petals.color', Q('$or', ['red', 'blue']))
    garden.search('flowers.petals.color', hue)

    petals = Q('flowers.petals', Q('$count', Q('$gt', 5)))
    compound_criteria = hue & petals
    garden.search('flowers.petals.color', compound_criteria)
    """
    # set root
    # split dot-notated search term, first element corresponds
    # to the root attribute
    terms = search_term.split('.')
    T, new_T = terms.pop(0), '.'.join(terms)
    if not T:
        yield obj
        raise StopIteration
    # get the field value at the current level
    obj = [getattr(obj, T)] if not \
            isinstance(obj, (list, set)) else (getattr(o, T) for o in obj)
    # in PY3.3 and greater, this is a perfect example
    # of when to use the `yield from` syntax
    for element in obj:
        for found in search(element, new_T, element):
            yield found
