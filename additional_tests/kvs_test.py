from unittest import TestCase
from uuid import uuid4

import redis

from api.config import BotjagwarConfig
from api.data.kvs import RedisPersistentSingleton


class Animal(RedisPersistentSingleton):
    """
    Implementation test for the persistent Singleton
    """

    def __init__(self):
        super(Animal, self).__init__()

    def init_attrs(self):
        self.noise = 'meow'
        self.legs = 4
        self.colour = 'white'
        self.speed = 12

    def upgrade_speed(self):
        self.speed *= 1.05

    def downgrade_speed(self):
        self.speed *= .95

    def run(self):
        print('speed:', self.speed)
        print('noise', self.noise)
        print('legs', self.legs)


class TestPersistentSingleton(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.singleton = Animal()
        cls.uuid = str(uuid4())
        cls.singleton.uuid = cls.uuid

    @classmethod
    def tearDownClass(cls):
        config = BotjagwarConfig()
        host = config.get('host', section='redis')
        password = config.get('password', section='redis')
        instance = redis.Redis(host=host, password=password)
        instance.flushall()

    def setUp(self):
        pass

    def tearDown(self):
        pass


    def test_instantiate_singleton(self):
        an = Animal()
        self.assertEqual(an.uuid, self.uuid)

    def test_set_value_singleton(self):
        an = Animal()
        t0 = str(uuid4())
        an.test0 = t0
        an2 = Animal()
        self.assertEqual(an2.test0, t0)

    def test_delete_singleton_value(self):
        an = Animal()
        with self.assertRaises(AttributeError):
            del an.speed
