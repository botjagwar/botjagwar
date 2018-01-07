from models import BaseEntry, List
from unittest.case import TestCase


class TestModels(TestCase):

    def test_instantiate_base(self):
        test = BaseEntry(
            test1=10,
            test2=20,
            test3=300
        )
        self.assertEquals(test.test1, 10)
        self.assertEquals(test.test2, 20)
        self.assertEquals(test.test3, 300)

    def test_instantiate_child_class_additional_properties(self):
        class QingChuan(BaseEntry):
            _additional = True
            properties_types = {
                "test1": int,
                "test2": int
            }

        test = QingChuan(
            test1=1,
            test2=2,
            test3=u"klew"  # additional!
        )
        self.assertEquals(test.test1, 1)
        self.assertEquals(test.test2, 2)
        self.assertEquals(test.test3, u"klew")

    def test_instantiate_child_class_no_additional_properties(self):

        class GuoHang(BaseEntry):
            _additional = False
            properties_types = {
                "test1": int,
                "test2": int
            }

        def do_checks():
            test = GuoHang(
                test1=1,
                test2=2,
                test3=u"klew"  # additional!
            )
            self.assertEquals(test.test1, 1)
            self.assertEquals(test.test2, 2)
            self.assertEquals(test.test3, u"klew")

        self.assertRaises(AttributeError, do_checks)

    def test_serialise_with_list(self):

        class YunHang(BaseEntry):
            _additional = False
            properties_types = {
                "test1": int,
                "test2": int,
                'test3obj': List
            }

        test = YunHang(test1=1, test2=2, test3obj=List(['qw', 'dlk']))
        print test.to_dict()
        print dir(test)
