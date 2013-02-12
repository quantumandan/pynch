import unittest
from base import Model
from fields import *


class PynchTestSuite(unittest.TestCase):
    def setUp(self):
        class Flower(Model):
            name = StringField()

        class Gardener(Model):
            name = StringField(required=True)
            instructor = ReferenceField('self')

            def __str__(self):
                return self.name

        class BugStomper(Model):
            stomper = ReferenceField(Gardener)
            number_squashed = IntegerField()

        class Garden(Model):
            acres = DecimalField()
            gardener = ReferenceField(Gardener)
            flowers = ListField(Flower)

        self.Gardener = Gardener
        self.BugStomper = BugStomper
        self.Garden = Garden
        self.Flower = Flower

    def test_required(self):
        pass

    def test_unique_with(self):
        pass

    def test_referencefield(self):
        pass

    def test_listfield(self):
        pass

    def test_dictfield(self):
        pass

    def test_generatorfield(self):
        pass

    def test_stringfield(self):
        pass

    def test_integerfield(self):
        pass

    def test_floatfield(self):
        pass

    def test_this(self):
        jones = self.Gardener(name='Mr. Jones')
        me = self.Gardener(name='Jim', instructor=jones)
        stomper = self.BugStomper(stomper=jones, number_squashed=0)
        garden = self.Garden(gardener=me)
        garden.flowers = [self.Flower(name='rose'), self.Flower(name='daisy')]

        class Phoo(Model):
            hell = ListField(StringField())
            bliss = ListField(ReferenceField(self.Gardener))

        # garden.flowers.append(1)
        # self.Garden.validate(garden)
        p = Phoo()
        p.bliss = []
        p.bliss.append('me')
        p.hell = []
        p.hell.append(1)
        p.validate()
        # print p._to_mongo()

if __name__ == '__main__':
    unittest.main()
