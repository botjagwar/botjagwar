
import threading


def threaded(f):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=f, args=args, kwargs=kwargs)
        thread.setDaemon(False)
        thread.start()
    return wrapper
