import datetime
import threading
import time


def threaded(f):
    import queue
    def wrapped_f(q, *args, **kwargs):
        '''this function calls the decorated function and puts the
        result in a queue'''
        ret = f(*args, **kwargs)
        q.put(ret)

    def wrap(*args, **kwargs):
        '''this is the function returned from the decorator. It fires off
        wrapped_f in a new thread and returns the thread object with
        the result queue attached'''

        q = queue.Queue()

        t = threading.Thread(target=wrapped_f, args=(q,)+args, kwargs=kwargs)
        t.daemon = False
        t.start()
        t.result_queue = q
        return t

    return wrap


def time_this(identifier='function'):
    def _time_this(f):
        def wrapper(*args, **kwargs):
            t0 = datetime.datetime.now()

            ret = f(*args, **kwargs)

            t1 = datetime.datetime.now()
            dt = t1 - t0
            d = dt.seconds * 1000 + dt.microseconds / 1000
            print(("%s took %2.2f seconds to execute" % (identifier, d/1000.)))
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
                    time.sleep(time_between_retries)
                else:
                    raise e

        return wrapper
    return _retry_on_fail