import datetime
import threading
import time


def threaded(f):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=f, args=args, kwargs=kwargs)
        thread.setDaemon(False)
        thread.start()
    return wrapper


def time_this(identifier='function'):
    def _time_this(f):
        def wrapper(*args, **kwargs):
            t0 = datetime.datetime.now()

            ret = f(*args, **kwargs)

            t1 = datetime.datetime.now()
            dt = t1 - t0
            d = dt.seconds * 1000 + dt.microseconds / 1000
            print ("%s took %2.2f seconds to execute" % (identifier, d/1000.))
            return ret

        return wrapper
    return _time_this


def retry_on_fail(exceptions, retries=5, time_between_retries=1):
    def _retry_on_fail(f):
        def wrapper(*args, **kwargs):
            m_retries = 0
            try:
                return f(*args, **kwargs)
            except exceptions as e:
                if m_retries <= retries:
                    m_retries += 1
                    time.sleep(time_between_retries)
                else:
                    raise e

        return wrapper
    return _retry_on_fail