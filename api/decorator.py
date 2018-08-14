import datetime
import threading
import time


def critical_section(cs_lock: threading.Lock):
    def _critical_section(f):
        def _critical_section_wrapper(*args, **kwargs):
            cs_lock.acquire()
            ret = f(*args, **kwargs)
            cs_lock.release()
            return ret
        return _critical_section_wrapper
    return _critical_section


def singleton(class_):
    instances = {}
    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]
    return getinstance


def threaded(f):
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

