import pickle
from uuid import uuid4

from api.config import BotjagwarConfig


class KeyValueStoreAPI(object):
    def __init__(self):
        self.kvstore = {}
        self.identifier = None

    def __del__(self):
        del self.kvstore

    def set_identifier(self, class_):
        self.identifier = class_.__name__ + '/' + str(uuid4()) + '/'

    def cache_value(self, value):
        def cache_value_wrapper(f):
            def wrapper(*args, **kwargs):
                key = str(self.identifier) + 'cache/' + str(value) + '_'.join([str(s) for s in args[1:]])
                if key not in self.kvstore:
                    v = f(*args, **kwargs)
                    self._set_attribute(key, pickle.dumps(v))
                    print('funccall', key, v)
                    return v
                else:
                    v = pickle.loads(self.kvstore[key])
                    print('kvstore', key, v)
                    return

            return wrapper
        print(self.kvstore)
        return cache_value_wrapper

    def _get_attribute(self, key):
        data = self.kvstore[key]
        if data is not None:
            return data
        else:
            raise KeyError(key, ' was not found.')

    def _has_key(self, key):
        return key in self.kvstore

    def get_attribute(self):
        def wrapper(objekt, attribute):
            key = str(self.identifier) + 'attribute/' + str(attribute)
            return pickle.loads(self._get_attribute(key))

        return wrapper

    def _set_attribute(self, attribute, value):
        self.kvstore[attribute] = value

    def set_attribute(self):
        def wrapper(objekt, attribute, value):
            key = str(self.identifier) + 'attribute/' + attribute
            value = value
            self._set_attribute(key, pickle.dumps(value))
            return None
        return wrapper


class RedisWrapperAPI(KeyValueStoreAPI):
    def __init__(self, host='default', password='default', singleton=False, persistent=False, identifier='default'):
        import redis
        config = BotjagwarConfig()
        if host == 'default':
            host = config.get('host', section='redis')
        if password == 'default':
            password = config.get('password', section='redis')

        self.singleton = singleton
        self.persistent = persistent
        self.attributes = set()
        self.instance = redis.Redis(host=host, password=password)
        if identifier == 'default':
            self.set_identifier(self.__class__)
        else:
            self.identifier = identifier + '/'

    def set_client_class(self, client_class):
        self.client_class = client_class

    def set_identifier(self, class_):
        KeyValueStoreAPI.set_identifier(self, self.__class__)
        if hasattr(self, 'singleton'):
            if self.singleton:
                self.identifier = class_.__name__ + '/'

    @property
    def kvstore(self):
        d = {}
        for att in self.attributes:
            d[att] = self.instance.get(att)
        return d

    def __del__(self):
        if hasattr(self, 'persistent'):
            if not self.persistent:
                if hasattr(self, 'attributes'):
                    for key in self.attributes:
                        self.instance.delete(key)

                if hasattr(self, 'instance'):
                    self.instance.close()

    def _set_attribute(self, attribute, value):
        self.attributes.add(attribute)
        return self.instance.set(attribute, value)

    def _get_attribute(self, attribute):
        data = self.instance.get(attribute)
        if data is not None:
            return data
        else:
            raise KeyError(attribute)


class RedisDictionary(RedisWrapperAPI):
    @classmethod
    def from_identifier(cls, identifier):
        instance = cls()
        instance.identifier = identifier
        return instance

    def __init__(self, **kwargs):
        RedisWrapperAPI.__init__(self)

    def __delitem__(self, key: str):
        assert isinstance(key, str)
        rkey = self.identifier + 'item/' + key
        self.instance.delete(rkey)

    def __setitem__(self, key: str, value):
        assert isinstance(key, str)
        rkey = self.identifier + 'item/' + key
        self.instance.set(rkey, pickle.dumps(value, 4))

    def __getitem__(self, item: str):
        assert isinstance(item, str)
        rkey = self.identifier + 'item/' + item
        data = self.instance.get(rkey)
        if data is None:
            raise KeyError(item)

        return pickle.loads(data)

    def __del__(self):
        keys = self.instance.keys()
        print(self.identifier, keys)
        for k in keys:
            if self.identifier in str(k):
                self.instance.delete(k)


class KvsPersistentClass(object):
    def __setattr__(self, key, value):
        return self.kvs.set_attribute()(self, key, value)

    def __getattr__(self, item):
        return self.kvs.get_attribute()(self, item)


class RedisPersistentClass(KvsPersistentClass):
    kvs = RedisWrapperAPI(persistent=True)

    @property
    def kvstore(self):
        return self.kvs.kvstore

    def __getstate__(self):
        return self.kvs.kvstore

    def __setstate__(self, state: dict):
        for k, v in state.items():
            setattr(self, k, v)


class RedisPersistentSingleton(RedisPersistentClass):
    kvs = RedisWrapperAPI(persistent=True, singleton=True)

    def __init__(self):
        self.kvs.set_identifier(self.__class__)

    @property
    def kvstore(self):
        return self.kvs.kvstore
