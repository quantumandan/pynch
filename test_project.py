from test_settings import settings
from pynch.base import Model
from pynch.fields import *
from pynch.errors import *


class Base(Model):
    _meta = {'database': settings['Base_db']}


class Person(Base):
    name = StringField(required=True)

    def __str__(self):
        return self.name


class Bug(Base):
    munched = ListField(ReferenceField('Flower'))
    number_eyes = IntegerField()
    number_legs = IntegerField()


class Flower(Base):
    name = StringField(required=True)

    def __str__(self):
        return self.name


class Gardener(Person):
    _meta = {'database': settings['Gardener_db']}
    instructor = ReferenceField('self')
    picked = SetField(ReferenceField(Flower))
    planted = SetField(ReferenceField(Flower), disjoint_with='picked')


class BugStomper(Gardener):
    squashed = ListField(ReferenceField(Bug))


class Garden(Base):
    _meta = {'database': settings['Garden_db']}
    acres = FloatField()
    gardener = ReferenceField(Gardener,  unique_with=['bug_stomper'])
    flowers = ListField(ReferenceField(Flower))
    stomper = ReferenceField(BugStomper)
