import pickle
from uuid import uuid4


class KeyValueStoreAPI(object):
    def __init__(self):
        self.kvstore = {}
        self.identifier = None

    def __del__(self):
        del self.kvstore

    def set_identifier(self, class_):
        self.identifier = f"{class_.__name__}/{str(uuid4())}/"

    def cache_value(self, value):
        def cache_value_wrapper(f):
            def wrapper(*args, **kwargs):
                key = (
                    str(self.identifier)
                    + "cache/"
                    + str(value)
                    + "_".join([str(s) for s in args[1:]])
                )
                if key not in self.kvstore:
                    v = f(*args, **kwargs)
                    self._set_attribute(key, pickle.dumps(v))
                    print("funccall", key, v)
                    return v

                v = pickle.loads(self.kvstore[key])
                print("kvstore", key, v)
                return

            return wrapper

        print(self.kvstore)
        return cache_value_wrapper

    def _get_attribute(self, key):
        data = self.kvstore[key]
        if data is not None:
            return data

        raise KeyError(key, " was not found.")

    def _has_key(self, key):
        return key in self.kvstore

    def get_attribute(self):
        def wrapper(objekt, attribute):
            key = f"{str(self.identifier)}attribute/{str(attribute)}"
            return pickle.loads(self._get_attribute(key))

        return wrapper

    def _set_attribute(self, attribute, value):
        self.kvstore[attribute] = value

    def set_attribute(self):
        def wrapper(objekt, attribute, value):
            key = f"{str(self.identifier)}attribute/{attribute}"
            value = value
            self._set_attribute(key, pickle.dumps(value))
            return None

        return wrapper


class KvsPersistentClass(object):
    def __setattr__(self, key, value):
        return self.kvs.set_attribute()(self, key, value)

    def __getattr__(self, item):
        return self.kvs.get_attribute()(self, item)
