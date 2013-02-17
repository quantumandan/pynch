import unittest
from pynch.base import Model
from pynch.fields import *
from pynch.db import DB


class BaseFlora(Model):
    _meta = {'database': DB('test', 'localhost', 27017)}


class Flower(BaseFlora):
    name = StringField()


class Gardener(BaseFlora):
    name = StringField(required=True, primary_key=True)
    instructor = ReferenceField('self')

    # def __str__(self):
    #     return self.name


class BugStomper(Gardener):
    _meta = {'database': DB('test', 'localhost', 27017)}
    stomper = ReferenceField('Gardener')
    number_squashed = IntegerField()


class Garden(BaseFlora):
    acres = FloatField()
    gardener = ReferenceField(Gardener,  unique_with=['bug_stomper'])
    flowers = ListField(ReferenceField(Flower))
    bug_stomper = ReferenceField(BugStomper)


class PynchTestSuite(unittest.TestCase):
    def setUp(self):
        self.Gardener = Gardener
        self.BugStomper = BugStomper
        self.Garden = Garden
        self.Flower = Flower

    def test_required__simple_types(self):
        class Doc_A(Model):
            _meta = {'database': DB('test', 'localhost', 27017)}
            field1 = StringField(required=True)
            field2 = IntegerField(required=True)

        document = Doc_A(field1='hello', field2=1)
        document.validate()
        document.save()
        doc_a = Doc_A.find_one()
        # print doc_a.field1

    def test_no_pk(self):
        pass

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

    def test_reference_field(self):
        pass

    def test_list_field(self):
        pass

    def test_dict_field(self):
        pass

    def test_generator_field(self):
        pass

    def test_string_field(self):
        pass

    def test_integer_field(self):
        pass

    def test_floatfield(self):
        pass

    def test_this(self):
        jones = self.Gardener(name='Mr. Jones')
        jones.save()
        me = self.Gardener(name='Jim', instructor=jones)
        me.save()
        m = Gardener.find(name='Jim')
        x = [Gardener.to_python(y) for y in m]
        # print x[0].__dict__['instructor'].__dict__.keys()
        print x[1].__dict__
        stomper = self.BugStomper(stomper=jones)
        stomper.validate()
        stomper.save()
        garden = self.Garden(gardener=me, bug_stomper=stomper)
        garden.acres = 0.25
        garden.flowers = [self.Flower(name='rose'), self.Flower(name='daisy')]

        class Phoo(Model):
            _meta = {'database': DB('test', 'localhost', 27017)}
            hell = ListField(StringField())
            bliss = ListField(ReferenceField(self.Gardener))

        garden.validate()
        # print garden.to_mongo()
        garden.save()
        g = garden.find_one()
        print g.gardener.instructor
        # phoo = Phoo(hell=['a', 'b', 'c'], bliss=[me, jones])
        # print phoo.to_mongo()
        # phoo.save()
        # p = Phoo.find_one()
        # print garden.to_mongo()
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
