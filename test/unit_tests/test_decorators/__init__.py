from random import randint
from time import sleep
from unittest import TestCase

from api.decorator import run_once, singleton, threaded

s = ""


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

    def test_threaded(self):

        @threaded
        def function1():
            global s
            s += "x"
            sleep(0.4)

        def function2():
            global s
            s += "y"
            sleep(0.2)

        function2()
        function1()
        self.assertEqual(s, "yx")

    def test_singleton(self):
        @singleton
        class ThisIsMySingleton(object):
            def __init__(self):
                self.incrementing_counter = 1

            @property
            def increment(self):
                self.incrementing_counter += 1
                return self.incrementing_counter

        def test1():
            s = ThisIsMySingleton()
            return s.increment

        def test2():
            s = ThisIsMySingleton()
            return s.increment

        test1()
        test2()
        r = ThisIsMySingleton()
        self.assertEqual(r.incrementing_counter, 3)
