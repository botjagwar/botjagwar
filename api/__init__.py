VERSION = None


def get_version():
    global VERSION
    if VERSION is not None:
        return VERSION

    with open("/opt/botjagwar/data/version", "r") as f:
        VERSION = f.read().strip("\n")

    return VERSION


__all__ = ["get_version"]
