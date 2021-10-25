from random import randint
from unittest import TestCase

from api.decorator import run_once


class DecoratorsTest(TestCase):
    def test_run_once(self):
        class M(object):
            @run_once
            def get_it(self):
                return randint(10000, 10000000)

        obj = M()
        result1 = obj.get_it()
        result2 = obj.get_it()
        self.assertEqual(result1, result2)
