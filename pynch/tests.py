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


if __name__ == '__main__':
    unittest.main()
