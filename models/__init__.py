class BaseEntry(object):
    _additional = True
    types = {}
    properties = {}

    def __init__(self, **properties):
        for attribute, value in properties.items():
            self.add_attribute(attribute, value)

    def add_attribute(self, name, value):
        if name not in self.types and not self._additional:
            raise AttributeError("Unspecified Attribute '%s' not allowed in '%s' object" % (
                name, self.__class__.__name__))
        else:
            self.properties[name] = value

