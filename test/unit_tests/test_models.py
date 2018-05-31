import copy
from unittest.case import TestCase

from object_model import TypeCheckedObject, List
from object_model.word import Entry


class TestModels(TestCase):

    def test_instantiate_base(self):
        test = TypeCheckedObject(
            test1=10,
            test2=20,
            test3=300
        )
        self.assertEqual(test.test1, 10)
        self.assertEqual(test.test2, 20)
        self.assertEqual(test.test3, 300)

    def test_instantiate_child_class_additional_properties(self):
        class QingChuan(TypeCheckedObject):
            _additional = True
            properties_types = {
                "test1": int,
                "test2": int
            }

        test = QingChuan(
            test1=1,
            test2=2,
            test3="klew"  # additional!
        )
        self.assertEqual(test.test1, 1)
        self.assertEqual(test.test2, 2)
        self.assertEqual(test.test3, "klew")

    def test_instantiate_child_class_no_additional_properties(self):

        class GuoHang(TypeCheckedObject):
            _additional = False
            properties_types = {
                "test1": int,
                "test2": int
            }

        def do_checks():
            test = GuoHang(
                test1=1,
                test2=2,
                test3="klew"  # additional!
            )
            self.assertEqual(test.test1, 1)
            self.assertEqual(test.test2, 2)
            self.assertEqual(test.test3, "klew")

        self.assertRaises(AttributeError, do_checks)

    def test_serialise_with_list(self):

        class YunHang(TypeCheckedObject):
            _additional = False
            properties_types = {
                "test1": int,
                "test2": int,
                'test3obj': List
            }

        test = YunHang(test1=1, test2=2, test3obj=List(['qw', 'dlk']))

        self.assertTrue(isinstance(test.test1, int))
        self.assertTrue(isinstance(test.test2, int))
        self.assertTrue(isinstance(test.test3obj, List))


class TestEntry(TestCase):
    def test_to_tuple(self):
        entry = Entry(
            entry='1',
            part_of_speech='2',
            entry_definition=['3']
        )
        self.assertEqual(entry.entry, '1')
        self.assertEqual(entry.part_of_speech, '2')
        self.assertEqual(entry.entry_definition, ['3'])

    def test_deep_copy(self):
        old = Entry(
            entry='tasumaki',
            part_of_speech='2',
            entry_definition=['3']
        )
        new = copy.deepcopy(old)
        new.entry = 'wrong'
        new.entry_definition = ['potomaki']
        self.assertNotEqual(new.entry, old.entry)
        self.assertNotEqual(new.entry_definition, old.entry_definition)

    def test_less_than(self):
        entry1 = Entry(
            entry='1',
            part_of_speech='2',
            language='kl',
            entry_definition=['3']
        )
        entry2 = Entry(
            entry='2',
            part_of_speech='2',
            language='km',
            entry_definition=['3']
        )

        self.assertLess(entry1, entry2)

    def test_less_than_2(self):
        entry1 = Entry(
            entry='a',
            part_of_speech='i',
            language='kk',
            entry_definition=['3']
        )
        entry2 = Entry(
            entry='b',
            part_of_speech='i',
            language='kk',
            entry_definition=['3']
        )

        self.assertLess(entry1, entry2)

    def test_less_than_3(self):
        entry1 = Entry(
            entry='1',
            part_of_speech='2',
            language='kl',
            entry_definition=['3']
        )
        entry2 = Entry(
            entry='1',
            part_of_speech='3',
            language='kl',
            entry_definition=['4']
        )

        self.assertLess(entry1, entry2)