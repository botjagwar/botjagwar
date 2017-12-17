class BaseEntry(object):
    _additional = True
    properties_types = {}
    properties = {}

    def __init__(self, **properties):
        for attribute, value in properties.items():
            self.add_attribute(attribute, value)

    def __getattr__(self, item):
        if item in self.properties:
            return self.properties[item]
        else:
            raise AttributeError("%s object has no attribute '%s'"  % (
                self.__class__.__name__,
                item
            ))

    def add_attribute(self, name, value):
        """
        Sets an attribute to the class
        properties_types contains the types expected for each property. If a property
        is being set and doesn't match the specified type, AttributeError will be raised
        If _additional is False and an unspecified attribute is being added. An error is raised
        If _additional is True, an unspecified attribute can be added.
        :param name:
        :param value:
        :return:
        """
        if name in self.properties_types:
            if isinstance(value, self.properties_types[name]):
                self.properties[name] = value
            else:
                raise AttributeError("%s attribute '%s' expects %s, not %s" % (
                    self.__class__.__name__,
                    name,
                    self.properties_types[name].__name__,
                    value.__class__.__name__
                ))
        else:
            if not self._additional:
                raise AttributeError("Unspecified Attribute '%s' not allowed in '%s' object" % (
                    name, self.__class__.__name__))
            else:
                self.properties[name] = value