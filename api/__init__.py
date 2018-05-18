VERSION = None


def get_version():
    global VERSION
    if VERSION is not None:
        return VERSION
    else:
        with open('data/version', 'r') as f:
            VERSION = f.read()
    return VERSION


__all__ = ['get_version']