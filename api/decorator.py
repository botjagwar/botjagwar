import datetime
import multiprocessing
import threading
import time
from typing import List, Tuple, Set


def critical_section(cs_lock: threading.Lock):
    """
    Decorator which uses acquires the specified lock when entering in the decorated function
    and releases it once out of the decorated function.
    :param cs_lock:
    :return:
    """
    def _critical_section(f):
        def _critical_section_wrapper(*args, **kwargs):
            cs_lock.acquire()
            ret = f(*args, **kwargs)
            cs_lock.release()
            return ret
        return _critical_section_wrapper
    return _critical_section


class run_once(object):
    """
    Decorator for run-once methods
    """
    __slots__ = ("func", "result", "methods")

    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kw):
        try:
            return self.result
        except AttributeError:
            self.result = self.func(*args, **kw)
            return self.result

    def __get__(self, instance, cls):
        method = self.func.__get__(instance, cls)
        try:
            return self.methods[method]
        except (AttributeError, KeyError):
            decorated = run_once(method)
            try:
                self.methods[method] = decorated
            except AttributeError:
                self.methods = {method: decorated}
            return decorated

    def __eq__(self, other):
        return isinstance(other, run_once) and other.func == self.func

    def __hash__(self):
        return hash(self.func)


def singleton(cls):
    class SingletonCreationError(Exception):
        pass

    class SingleClass(cls, object):
        """ The real singleton. """
        _instance = None
        __module__ = cls.__module__
        __doc__ = cls.__doc__

        def __new__(cls, *args, **kwargs):
            if SingleClass._instance is None:
                try:
                    SingleClass._instance = super(SingleClass, cls).__new__(cls, *args, **kwargs)
                except TypeError as error:
                    raise SingletonCreationError(f'Unexpected arguments: {args} and {kwargs}') from error
                SingleClass._instance._sealed = False

            return SingleClass._instance

        def __init__(self):
            if not getattr(self, '_sealed', False):
                super(SingleClass, self).__init__()
                self._sealed = True

    SingleClass.__name__ = cls.__name__
    return SingleClass


def threaded(f):
    def wrap(*args, **kwargs):
        t = threading.Thread(target=f, args=args, kwargs=kwargs)
        t.daemon = False
        t.start()

    return wrap


def separate_process(f):
    """
    Function runs in a separate, daemon thread
    :param f:
    :return:
    """
    def wrap(*args, **kwargs):
        t = multiprocessing.Process(target=f, args=args, kwargs=kwargs)
        t.start()

    return wrap


def catch_exceptions(*exceptions):
    def wrapper_catch_exceptions(f):
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except exceptions as exc:
                return None

        return wrapper
    return wrapper_catch_exceptions


def time_this(identifier=''):
    def _time_this(f):
        def wrapper(*args, **kwargs):
            t0 = datetime.datetime.now()

            ret = f(*args, **kwargs)

            t1 = datetime.datetime.now()
            dt = t1 - t0
            d = dt.seconds * 1000 + dt.microseconds / 1000
            if identifier == 'function':
                print((f"%s took %2.6f seconds to execute" %
                      (identifier, d / 1000.)))
            else:
                print((f"%s took %2.6f seconds to execute" %
                      (f.__name__, d / 1000.)))

            return ret

        return wrapper
    return _time_this


def retry_on_fail(exceptions: [Tuple[Exception], Set[Exception], List[Exception]], retries=5, time_between_retries=1):
    def _retry_on_fail(f):
        def wrapper(*args, **kwargs):
            m_retries = 0
            while True:
                try:
                    return f(*args, **kwargs)
                except exceptions as handled_error:
                    if m_retries <= retries:
                        m_retries += 1
                        print('Error:', handled_error, '%d' % m_retries)
                        time.sleep(time_between_retries)
                    else:
                        raise handled_error

        return wrapper
    return _retry_on_fail
