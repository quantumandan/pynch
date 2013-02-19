from test_settings import settings
from pynch.base import Model
from pynch.fields import *
from pynch.errors import *


class Base(Model):
    _meta = {'database': settings['Base_db']}


class Person(Base):
    name = StringField(required=True, primary_key=True)


class Bug(Base):
    munched = ListField(ReferenceField('Flower'))


class Flower(Base):
    name = StringField(required=True)


class Gardener(Person):
    instructor = ReferenceField('self')
    picked = ListField(ReferenceField('Flower'))
    planted = ListField(ReferenceField('Flower'), unique_with='picked')

    def __str__(self):
        return self.name


class BugStomper(Gardener):
    _meta = {'database': settings['BugStomper_db']}
    stomper = ReferenceField('Gardener')
    squashed = IntegerField()


class Garden(Base):
    acres = FloatField()
    gardener = ReferenceField(Gardener,  unique_with=['bug_stomper'])
    flowers = ListField(ReferenceField('Flower'))
    bug_stomper = ReferenceField(BugStomper)
