import unittest
from pynch.db import DB
from pynch.model import Model, PrimaryKey
from pynch.query import search
from pynch.fields import *
from pynch.errors import *
from test_project import *


class PynchSanityCheckTestSuite(unittest.TestCase):
    """
    Since introspection is involved at the module level, the
    first suite of tests does some basic sanity checking on a
    static project.
    """
    def setUp(self):
        Garden.pynch.collection.remove()

    def test_run_suite_from_sample_project(self):
        # populate garden
        jones = BugStomper(name='Mr. Jones')
        me = Gardener(name='Jim', instructor=jones)
        garden = Garden(gardener=me, stomper=jones)
        garden.acres = 0.25
        garden.flowers = [Flower(name='rose'), Flower(name='daisy')]
        garden.save()
        
        x = Garden.pynch.get(_id=garden.pk)
        self.assertTrue(x.gardener.name == 'Jim')
        
        flower_names = [flower.name for flower in x.flowers]
        self.assertListEqual(flower_names, ['rose', 'daisy'])
        self.assertTrue(x.gardener.instructor.name == 'Mr. Jones')
        self.assertEquals(x.pk, garden.pk)
        # self.assertEquals(x, garden)
        
        y = BugStomper.pynch.get(_id='Mr. Jones')
        self.assertTrue(y.name == 'Mr. Jones')

    def test_run_suite_fron_inlined_classes(self):
        from pynch.db import DB

        class WorkingGardener(Model):
            _meta = {'database': DB(name='mygarden'), 'write_concern': 1}
            name = StringField(primary_key=True)
            instructor = ReferenceField('self')

            def __str__(self):
                return self.name

        class TeachingGarden(Model):
            _meta = {'database': DB(name='mygarden'), 'write_concern': 1}
            _id = PrimaryKey()
            acres = FloatField()
            gardeners = ListField(ReferenceField(WorkingGardener))

        botanist = WorkingGardener(name='MrJones')
        person = WorkingGardener(name='me', instructor=botanist)
        garden = TeachingGarden(acres=0.25, gardeners=[person, botanist])
        garden.save()
        g = TeachingGarden.pynch.get(_id=garden.pk)
        self.assertEquals(g.pk, garden.pk)
        names = list(name for name in search(g, 'gardeners.name'))
        self.assertEquals(names, ['me', 'MrJones'])
        self.assertEquals(g, garden)

        botanist2 = WorkingGardener(name='MrJones2')
        person2 = WorkingGardener(name='me2', instructor=botanist2)
        garden2 = TeachingGarden(acres=0.25, gardeners=[person2, botanist2])
        garden2.save()

        to_raise = lambda: TeachingGarden.pynch.get(acres=0.25)
        self.assertRaises(QueryException, to_raise)

        garden2.delete()
        garden.delete()
        # answer = TeachingGarden.pynch.get(acres=0.25)

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
        mongo = A.pynch.collection.find_one({'_id': mongo_id})
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
        mongo = A.pynch.collection.find_one({'_id': mongo_id})
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
        mongo = A.pynch.collection.find_one({'_id': mongo_id})
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
        mongo = A.pynch.collection.find_one({'_id': mongo_id})
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

# MODELS FOR TESTING SIMPLE TO COMPLEX PKS
class TestModel(Model):
    _meta = {'database': DB(name='test'), 'write_concern': 1}


class BasePkModel(Model):
    _meta = {'database': DB(name='complexpk'), 'write_concern': 0}


class DictModel(BasePkModel):
    _id = DictField({'a': StringField(),
                     'c': IntegerField()}, primary_key=True)


class CompoundModel(BasePkModel):
    _id = EmbeddedDocumentField(DictModel, primary_key=True)


class PKTestSuite(unittest.TestCase):
    def test_simple_pk(self):
        pass

    def test_pk_without_default_field_name(self):
        pass

    def test_dictionary_as_pk(self):
        # PK as a dictionary
        PK = {'a': 'b', 'c': 4}
        dict_doc = DictModel(_id=PK)
        dict_doc.save()
        self.assertEquals(dict_doc, DictModel.pynch.get(_id=PK))

    def test_embedded_document_as_pk(self):
        # PK as an embeddged document
        document1 = CompoundModel(_id=DictModel(my_doc={'a': 'key a', 'c': 3}))
        document2 = CompoundModel(_id=DictModel(my_doc={u'c': 2, u'a': u'b'}))
        document1.save()
        document2.save()

        test = CompoundModel.pynch.get(_id=document2.pk.to_mongo())
        self.assertEquals(test.pk.to_mongo(), document2.pk.to_mongo())
        # import pdb; pdb.set_trace();
        self.assertEquals(test, document2)

        class A(BasePkModel):
            xx = StringField()

            def __str__(self):
                return self.xx

        class PK(BasePkModel):
            field1 = ReferenceField(A)
            field2 = FloatField()

        class CompositeModel(BasePkModel):
            my_doc = ComplexPrimaryKey(PK, primary_key=True)
            name = StringField()

        my_doc = PK(field1=A(xx='0.27'), field2=2.0)
        document = CompositeModel(my_doc=my_doc, name='hello')
        document.save()

        x = CompositeModel.pynch.get(_id=document.pk.to_mongo())
        self.assertEquals(x.pk, document.pk)
        
        y = CompositeModel.pynch.get(_id=x.pk.to_mongo())
        self.assertEquals(x, y)
        
        z = CompositeModel.pynch.get(_id=y.pk.to_mongo())
        self.assertEquals(y, z)
        
        document.pk.field2 = 500.0
        document.save()
        
        w = CompositeModel.pynch.get(_id=document.pk.to_mongo())
        self.assertEquals(w, document)
        self.assertEquals(w.pk.field2, 500.0)

    def test_no_pk(self):
        pass


# class A(Base):
#     b = ListField(ReferenceField('B'))


# class B(Base):
#     c = ListField(ReferenceField('C'))


# class C(Base):
#     field1 = FloatField()
#     field2 = FloatField()


# class SearchTestSuite(unittest.TestCase):
#     def test_search(self):
#         a = A()
#         a.b = [B(), B(), B()]
#         for b in a.b:
#             b.c = [C(field1=1.0, field2=1.2),
#                    C(field1=1.0, field2=1.2)]

#         self.assertEquals([1.0] * 6, [x for x in search(a, 'b.c.field1')])

if __name__ == '__main__':
    unittest.main()
