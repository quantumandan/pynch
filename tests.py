import unittest
from pynch.base import Model
from pynch.db import DB
from pynch.fields import *
from pynch.errors import *
from test_project import *


class TestModel(Model):
    _meta = {'database': DB(name='test')}


class PynchTestSuite(unittest.TestCase):
    def test_this(self):
        jones = BugStomper(name='Mr. Jones')
        me = Gardener(name='Jim', instructor=jones)
        garden = Garden(gardener=me, stomper=jones)
        garden.acres = 0.25
        garden.flowers = [Flower(name='rose'), Flower(name='daisy')]
        garden.save()
        x = Garden._pynch.objects.find_one(acres=0.25)
        self.assertTrue(x.gardener.name == 'Jim')
        flower_names = [flower.name for flower in x.flowers]
        self.assertListEqual(flower_names, ['rose', 'daisy'])
        self.assertTrue(x.gardener.instructor.name == 'Mr. Jones')
        y = BugStomper._pynch.objects.find_one(name='Mr. Jones')
        self.assertTrue(y.name == 'Mr. Jones')

    def test_this2(self):
        from pynch.db import DB

        class WorkingGardener(Model):
            _meta = {'database': DB(name='mygarden')}
            name = StringField(required=True)
            instructor = ReferenceField('self')

            def __str__(self):
                return self.name

        class TeachingGarden(Model):
            _meta = {'database': DB(name='mygarden')}
            acres = DecimalField()
            gardeners = ListField(ReferenceField(WorkingGardener))

        botanist = WorkingGardener(name='MrJones')
        person = WorkingGardener(name='me', instructor=botanist)
        garden = TeachingGarden(acres=0.25, gardeners=[person, botanist])
        garden.save()
        g = TeachingGarden._pynch.objects.find_one(_id=garden.pk)

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


class StringFieldTestSuite(unittest.TestCase):
    def test_string_field(self):
        class A(TestModel):
            field = StringField()

        a = A()
        a.field = 'abc'
        self.assertEquals(a.field, 'abc')

        a = A(field='abc')
        self.assertEquals(a.field, 'abc')

    def test_string_field_as_pk(self):
        class A(TestModel):
            field = StringField(primary_key=True)

        a = A(field='abc')
        self.assertEquals(a.pk, 'abc')

    def test_string_field_as_db_field(self):
        class A(TestModel):
            field = StringField(db_field='new_field')

        a = A(field='abc')
        mongo_id = a.save().pk
        mongo = A._pynch.collection.find_one({'_id': mongo_id})
        self.assertTrue('new_field' in mongo)
        self.assertTrue(mongo['new_field'] == 'abc')

    def test_string_field_required(self):
        class A(TestModel):
            field = StringField(required=True)

        a = A()
        self.assertRaises(DocumentValidationException, a.validate)

    def test_string_field_choices(self):
        class A(TestModel):
            field = StringField(choices=['a', 'b', 'c'])
        a = A()
        for choice in A.field.choices:
            a.field = choice
            self.assert_(a.validate())

        a.field = 'X'
        self.assertRaises(ValidationException, a.validate)

    def test_string_field_unique_with(self):
        class A(TestModel):
            field1 = StringField(unique_with='field2')
            field2 = StringField()

        a = A(field1='a', field2='a')
        self.assertRaises(DocumentValidationException, a.validate)

        a = A()
        a.field1 = 'a'
        a.field2 = 'a'
        self.assertRaises(DocumentValidationException, a.validate)

    def test_string_field_unique(self):
        class A(TestModel):
            field = StringField()


class IntegerFieldTestSuite(unittest.TestCase):
    def test_integer_field(self):
        class A(TestModel):
            field = IntegerField()

        a = A()
        a.field = 123
        self.assertEquals(a.field, 123)

        a = A(field=123)
        self.assertEquals(a.field, 123)

        self.assertRaises(DocumentValidationException, lambda: A(field='abc'))

    def test_integer_field_as_pk(self):
        class A(TestModel):
            field = IntegerField(primary_key=True)

        a = A(field=123)
        self.assertEquals(a.pk, 123)

    def test_integer_field_as_db_field(self):
        class A(TestModel):
            field = IntegerField(db_field='new_field')

        a = A(field=123)
        mongo_id = a.save().pk
        mongo = A._pynch.collection.find_one({'_id': mongo_id})
        self.assertTrue('new_field' in mongo)
        self.assertTrue(mongo['new_field'] == 123)

    def test_integer_field_required(self):
        class A(TestModel):
            field = IntegerField(required=True)

        a = A()
        self.assertRaises(DocumentValidationException, a.validate)

    def test_integer_field_choices(self):
        class A(TestModel):
            field = IntegerField(choices=[1, 2, 3])
        a = A()
        for choice in A.field.choices:
            a.field = choice
            self.assert_(a.validate())

        a.field = 5
        self.assertRaises(DocumentValidationException, a.validate)

    def test_integer_field_unique_with(self):
        class A(TestModel):
            field1 = IntegerField(unique_with='field2')
            field2 = IntegerField()

        a = A(field1=1, field2=1)
        self.assertRaises(DocumentValidationException, a.validate)

        a = A()
        a.field1 = 1
        a.field2 = 1
        self.assertRaises(DocumentValidationException, a.validate)

    def test_integer_field_unique(self):
        class A(TestModel):
            field = IntegerField()


class FloatFieldTestSuite(unittest.TestCase):
    def test_float_field(self):
        class A(TestModel):
            field = FloatField()

        a = A()
        a.field = 0.123
        self.assertEquals(a.field, 0.123)

        a = A(field=0.123)
        self.assertEquals(a.field, 0.123)

        self.assertRaises(DocumentValidationException, lambda: A(field='abc'))

    def test_float_field_as_pk(self):
        class A(TestModel):
            field = FloatField(primary_key=True)

        a = A(field=0.123)
        self.assertEquals(a.pk, 0.123)

    def test_float_field_as_db_field(self):
        class A(TestModel):
            field = FloatField(db_field='new_field')

        a = A(field=0.123)
        mongo_id = a.save().pk
        mongo = A._pynch.collection.find_one({'_id': mongo_id})
        self.assertTrue('new_field' in mongo)
        self.assertTrue(mongo['new_field'] == 0.123)

    def test_float_field_required(self):
        class A(TestModel):
            field = FloatField(required=True)

        a = A()
        self.assertRaises(DocumentValidationException, a.validate)

    def test_float_field_choices(self):
        class A(TestModel):
            field = FloatField(choices=[1.0, 2.0, 3.0])
        a = A()
        for choice in A.field.choices:
            a.field = choice
            self.assert_(a.validate())

        a.field = 5.0
        self.assertRaises(DocumentValidationException, a.validate)

    def test_float_field_unique_with(self):
        class A(TestModel):
            field1 = FloatField(unique_with='field2')
            field2 = FloatField()

        a = A(field1=1.0, field2=1.0)
        self.assertRaises(DocumentValidationException, a.validate)

        a = A()
        a.field1 = 1.0
        a.field2 = 1.0
        self.assertRaises(DocumentValidationException, a.validate)

    def test_float_field_unique(self):
        class A(TestModel):
            field = FloatField()


class BooleanFieldTestSuite(unittest.TestCase):
    def test_boolean_field(self):
        class A(TestModel):
            field = BooleanField()

        a = A()
        a.field = True
        self.assertEquals(a.field, True)

        a = A(field=True)
        self.assertEquals(a.field, True)

    def test_boolean_field_as_pk(self):
        """
        Todo: boolean fields shouldnt be pk's
        """

    def test_boolean_field_as_db_field(self):
        class A(TestModel):
            field = BooleanField(db_field='new_field')

        a = A(field=False)
        mongo_id = a.save().pk
        mongo = A._pynch.collection.find_one({'_id': mongo_id})
        self.assertTrue('new_field' in mongo)
        self.assertTrue(mongo['new_field'] == False)

    def test_boolean_field_required(self):
        class A(TestModel):
            field = BooleanField(required=True)

        a = A()
        self.assertRaises(DocumentValidationException, a.validate)

    def test_boolean_field_choices(self):
        class A(TestModel):
            field = BooleanField(choices=[True, False])
        a = A()
        for choice in A.field.choices:
            a.field = choice
            self.assert_(a.validate())

        self.assertRaises(FieldTypeException, lambda: setattr(a, 'field', 5))

    def test_boolean_field_unique_with(self):
        class A(TestModel):
            field1 = BooleanField(unique_with='field2')
            field2 = BooleanField()

        a = A(field1=True, field2=True)
        self.assertRaises(DocumentValidationException, a.validate)

        a = A()
        a.field1 = False
        a.field2 = False
        self.assertRaises(DocumentValidationException, a.validate)

    def test_boolean_field_unique(self):
        class A(TestModel):
            field = BooleanField()


class A(Base):
    b = ListField(ReferenceField('B'))


class B(Base):
    c = ListField(ReferenceField('C'))


class C(Base):
    field1 = FloatField()
    field2 = FloatField()


class SearchTestSuite(unittest.TestCase):
    def test_search(self):
        a = A()
        a.b = [B(), B(), B()]
        for b in a.b:
            b.c = [C(field1=1.0, field2=1.2),
                   C(field1=1.0, field2=1.2)]

        self.assertEquals([1.0] * 6, [x for x in a.get('b.c.field1')])

if __name__ == '__main__':
    unittest.main()
