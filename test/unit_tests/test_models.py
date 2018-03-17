from models import TypeCheckedObject, List
from unittest.case import TestCase


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