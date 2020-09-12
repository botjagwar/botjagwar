import pickle
from uuid import uuid4


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
        return self.kvstore[key]

    def _has_key(self, key):
        return key in self.kvstore

    def get_attribute(self):
        def get_attribute_wrapper(f):
            def wrapper(objekt, attribute):
                key = str(self.identifier) + 'attribute/' + str(attribute)
                if not self._has_key(key):
                    raise AttributeError(self.__class__.__name__ + f' has no attribute {attribute}')
                else:
                    return pickle.loads(self._get_attribute(key))

            return wrapper
        return get_attribute_wrapper

    def _set_attribute(self, attribute, value):
        self.kvstore[attribute] = value

    def set_attribute(self):
        def set_attribute_wrapper(f):
            def wrapper(objekt, attribute, value):
                key = str(self.identifier) + 'attribute/' + attribute
                value = f(objekt, attribute, value)
                self._set_attribute(key, pickle.dumps(value))

            return wrapper
        return set_attribute_wrapper


class RedisWrapperAPI(KeyValueStoreAPI):
    def __init__(self, host='127.0.0.1', password='qwertyuiop'):
        import redis
        self.instance = redis.Redis(host=host, password=password)
        self.attributes = set()

    @property
    def kvstore(self):
        d = {}
        for att in self.attributes:
            d[att] = self.instance.get(att)
        return d

    def __del__(self):
        for key in self.attributes:
            self.instance.delete(key)

        self.instance.close()

    def _set_attribute(self, attribute, value):
        self.attributes.add(attribute)
        return self.instance.set(attribute, value)

    def _get_attribute(self, attribute):
        return self.instance.get(attribute)
