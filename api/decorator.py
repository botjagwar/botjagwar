import datetime
import threading
import time


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
        except (AttributeError,KeyError):
            decorated = run_once(method)
            try:
                self.methods[method] = decorated
            except AttributeError:
                self.methods = { method : decorated }
            return decorated

    def __eq__(self, other):
        return isinstance(other, run_once) and other.func == self.func

    def __hash__(self):
        return hash(self.func)


def singleton(class_):
    """
    Specify that a class is a singleton
    :param class_:
    :return:
    """
    instances = {}
    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]
    return getinstance


def threaded(f):
    """
    Function runs in a separate, daemon thread
    :param f:
    :return:
    """
    def wrap(*args, **kwargs):
        t = threading.Thread(target=f, args=args, kwargs=kwargs)
        t.daemon = False
        t.start()

    return wrap


def time_this(identifier='function'):
    def _time_this(f):
        def wrapper(*args, **kwargs):
            t0 = datetime.datetime.now()

            ret = f(*args, **kwargs)

            t1 = datetime.datetime.now()
            dt = t1 - t0
            d = dt.seconds * 1000 + dt.microseconds / 1000
            print(("%s took %2.6f seconds to execute" % (identifier, d/1000.)))
            return ret

        return wrapper
    return _time_this


def retry_on_fail(exceptions, retries=5, time_between_retries=1):
    def _retry_on_fail(f):
        def wrapper(*args, **kwargs):
            m_retries = 0
            try:
                return f(*args, **kwargs)
            except tuple(exceptions) as e:
                if m_retries <= retries:
                    m_retries += 1
                    print('Error:', e, '%d' % m_retries)
                    time.sleep(time_between_retries)
                else:
                    raise e

        return wrapper
    return _retry_on_fail
