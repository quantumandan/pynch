import unittest
from pynch.base import Model
from pynch.fields import *
from pynch.errors import *
from test_project import *


class PynchTestSuite(unittest.TestCase):
    # def test_required__simple_types(self):
    #     class Doc_A(Model):
    #         _meta = {'database': DB('test', 'localhost', 27017)}
    #         field1 = StringField(required=True)
    #         field2 = IntegerField(required=True)

    #     document = Doc_A(field1='hello', field2=1)
    #     document.validate()
    #     document.save()
    #     doc_a = Doc_A.find_one()
        # print doc_a.field1

    def test_this(self):
        jones = BugStomper(name='Mr. Jones')
        jones.save()
        me = Gardener(name='Jim', instructor=jones)
        me.save()
        m = Gardener.find(name='Jim')
        x = [Gardener.to_python(y) for y in m]
        # print x[0].__dict__['instructor'].__dict__.keys()
        garden = Garden(gardener=me, stomper=jones)
        garden.acres = 0.25
        garden.flowers = [Flower(name='rose'), Flower(name='daisy')]
        garden.save()

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
        class A(Model):
            field = StringField()

        a = A()
        a.field = 'abc'
        self.assertEquals(a.field, 'abc')

        a = A(field='abc')
        self.assertEquals(a.field, 'abc')

        self.assertRaises(FieldTypeException, lambda: A(field=123))

    def test_string_field_as_pk(self):
        class A(Model):
            field = StringField(primary_key=True)

        a = A(field='abc')
        self.assertEquals(a.pk, 'abc')

    def test_string_field_as_db_field(self):
        class A(Model):
            field = StringField(db_field='new_field')

        a = A(field='abc')
        mongo = a.to_mongo()
        self.assertTrue('new_field' in mongo)
        self.assertTrue(mongo['new_field'] == 'abc')

    def test_string_field_required(self):
        class A(Model):
            field = StringField(required=True)

        a = A()
        self.assertRaises(DocumentValidationException, a.validate)

    def test_string_field_choices(self):
        class A(Model):
            field = StringField(choices=['a', 'b', 'c'])
        a = A()
        for choice in A.field.choices:
            a.field = choice
            self.assert_(a.validate())

        a.field = 'X'
        self.assertRaises(ValidationException, a.validate)

    def test_string_field_unique_with(self):
        class A(Model):
            field1 = StringField(unique_with='field2')
            field2 = StringField()

        a = A(field1='a', field2='a')
        self.assertRaises(DocumentValidationException, a.validate)

        a = A()
        a.field1 = 'a'
        a.field2 = 'a'
        self.assertRaises(DocumentValidationException, a.validate)

    def test_string_field_unique(self):
        class A(Model):
            field = StringField()


class IntegerFieldTestSuite(unittest.TestCase):
    def test_integer_field(self):
        class A(Model):
            field = IntegerField()

        a = A()
        a.field = 123
        self.assertEquals(a.field, 123)

        a = A(field=123)
        self.assertEquals(a.field, 123)

        self.assertRaises(FieldTypeException, lambda: A(field='abc'))

    def test_integer_field_as_pk(self):
        class A(Model):
            field = IntegerField(primary_key=True)

        a = A(field=123)
        self.assertEquals(a.pk, 123)

    def test_integer_field_as_db_field(self):
        class A(Model):
            field = IntegerField(db_field='new_field')

        a = A(field=123)
        mongo = a.to_mongo()
        self.assertTrue('new_field' in mongo)
        self.assertTrue(mongo['new_field'] == 123)

    def test_integer_field_required(self):
        class A(Model):
            field = IntegerField(required=True)

        a = A()
        self.assertRaises(DocumentValidationException, a.validate)

    def test_integer_field_choices(self):
        class A(Model):
            field = IntegerField(choices=[1, 2, 3])
        a = A()
        for choice in A.field.choices:
            a.field = choice
            self.assert_(a.validate())

        a.field = 5
        self.assertRaises(DocumentValidationException, a.validate)

    def test_integer_field_unique_with(self):
        class A(Model):
            field1 = IntegerField(unique_with='field2')
            field2 = IntegerField()

        a = A(field1=1, field2=1)
        self.assertRaises(DocumentValidationException, a.validate)

        a = A()
        a.field1 = 1
        a.field2 = 1
        self.assertRaises(DocumentValidationException, a.validate)

    def test_integer_field_unique(self):
        class A(Model):
            field = IntegerField()


class FloatFieldTestSuite(unittest.TestCase):
    def test_float_field(self):
        class A(Model):
            field = FloatField()

        a = A()
        a.field = 0.123
        self.assertEquals(a.field, 0.123)

        a = A(field=0.123)
        self.assertEquals(a.field, 0.123)

        self.assertRaises(FieldTypeException, lambda: A(field='abc'))

    def test_float_field_as_pk(self):
        class A(Model):
            field = FloatField(primary_key=True)

        a = A(field=0.123)
        self.assertEquals(a.pk, 0.123)

    def test_float_field_as_db_field(self):
        class A(Model):
            field = FloatField(db_field='new_field')

        a = A(field=0.123)
        mongo = a.to_mongo()
        self.assertTrue('new_field' in mongo)
        self.assertTrue(mongo['new_field'] == 0.123)

    def test_float_field_required(self):
        class A(Model):
            field = FloatField(required=True)

        a = A()
        self.assertRaises(DocumentValidationException, a.validate)

    def test_float_field_choices(self):
        class A(Model):
            field = FloatField(choices=[1.0, 2.0, 3.0])
        a = A()
        for choice in A.field.choices:
            a.field = choice
            self.assert_(a.validate())

        a.field = 5.0
        self.assertRaises(DocumentValidationException, a.validate)

    def test_float_field_unique_with(self):
        class A(Model):
            field1 = FloatField(unique_with='field2')
            field2 = FloatField()

        a = A(field1=1.0, field2=1.0)
        self.assertRaises(DocumentValidationException, a.validate)

        a = A()
        a.field1 = 1.0
        a.field2 = 1.0
        self.assertRaises(DocumentValidationException, a.validate)

    def test_float_field_unique(self):
        class A(Model):
            field = FloatField()


class BooleanFieldTestSuite(unittest.TestCase):
    def test_boolean_field(self):
        class A(Model):
            field = BooleanField()

        a = A()
        a.field = True
        self.assertEquals(a.field, True)

        a = A(field=True)
        self.assertEquals(a.field, True)

        self.assertRaises(FieldTypeException, lambda: A(field='abc'))

    def test_boolean_field_as_pk(self):
        """
        Todo: boolean fields shouldnt be pk's
        """

    def test_boolean_field_as_db_field(self):
        class A(Model):
            field = BooleanField(db_field='new_field')

        a = A(field=False)
        mongo = a.to_mongo()
        self.assertTrue('new_field' in mongo)
        self.assertTrue(mongo['new_field'] == False)

    def test_boolean_field_required(self):
        class A(Model):
            field = BooleanField(required=True)

        a = A()
        self.assertRaises(DocumentValidationException, a.validate)

    def test_boolean_field_choices(self):
        class A(Model):
            field = BooleanField(choices=[True, False])
        a = A()
        for choice in A.field.choices:
            a.field = choice
            self.assert_(a.validate())

        self.assertRaises(FieldTypeException, lambda: setattr(a, 'field', 5))

    def test_boolean_field_unique_with(self):
        class A(Model):
            field1 = BooleanField(unique_with='field2')
            field2 = BooleanField()

        a = A(field1=True, field2=True)
        self.assertRaises(DocumentValidationException, a.validate)

        a = A()
        a.field1 = False
        a.field2 = False
        self.assertRaises(DocumentValidationException, a.validate)

    def test_boolean_field_unique(self):
        class A(Model):
            field = BooleanField()

    #     class Phoo(Model):
    #         _meta = {'database': DB('test', 'localhost', 27017)}
    #         hell = ListField(StringField())
    #         bliss = ListField(ReferenceField(self.Gardener))

    #     garden.validate()
    #     # print garden.to_mongo()
    #     garden.save()
    #     g = garden.find_one()
    #     print g.gardener.instructor
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
