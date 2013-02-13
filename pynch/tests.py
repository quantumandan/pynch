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

        class BugStomper(Gardener):
            stomper = ReferenceField(Gardener)
            number_squashed = IntegerField()

        class Garden(Model):
            acres = IntegerField()
            gardener = ReferenceField(Gardener,  unique_with=['bug_stomper'])
            flowers = ListField(Flower)
            bug_stomper = ReferenceField(BugStomper)

        self.Gardener = Gardener
        self.BugStomper = BugStomper
        self.Garden = Garden
        self.Flower = Flower

    def test_required__simple_types(self):
        class Doc_A(Model):
            field1 = StringField(required=True)
            field2 = IntegerField(required=True)

        document = Doc_A(field1='hello')
        document.validate()

    def test_required__complex_types(self):
        pass

    def test_required__reference_types(self):
        pass

    def test_unique_with__simple_types(self):
        pass

    def test_unique_with__complex_types(self):
        pass

    def test_unique_with__reference_types(self):
        pass

    def test_field_value_is_an_inherited_type(self):
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
        garden = self.Garden(gardener=stomper, bug_stomper=stomper)
        garden.flowers = [self.Flower(name='rose'), self.Flower(name='daisy')]

        class Phoo(Model):
            hell = ListField(StringField())
            bliss = ListField(ReferenceField(self.Gardener))

        garden.validate()
        # self.Garden.validate(garden)
        # p = Phoo()
        # p.bliss = []
        # p.bliss.append('me')
        # p.hell = []
        # p.hell.append(1)
        # p.validate()
        # print p._to_mongo()

if __name__ == '__main__':
    unittest.main()
