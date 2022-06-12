class Property(object):
    def __init__(self, value, _type):
        if isinstance(value, _type):
            self.value = value

    def serialise(self):
        return str(self.value)


class List(Property):
    def __init__(self, value: list):
        Property.__init__(self, value, _type=list)

    def serialise(self):
        ret = []
        for value in self.value:
            if isinstance(value, Property):
                ret.append(value.serialise())
            else:
                ret.append(value)
        return ret


class TypeCheckedObject(object):
    _additional: bool = True
    properties: dict = {}
    additional_data_types: dict = {}
    properties_types: dict = {}
    node_mapper: list = []

    def __init__(self, **properties):
        for attribute, value in list(properties.items()):
            self.add_attribute(attribute, value)

    def __eq__(self, other):
        for pname, pvalue in list(self.properties.items()):
            if getattr(other, pname) != getattr(self, pname):
                return False

        return True

    def __dir__(self):
        return list(self.properties.keys())

    def serialise(self) -> dict:
        ret = {}
        for key in self.properties_types.keys():
            if hasattr(self, key):
                value = getattr(self, key)
                if isinstance(value, Property):
                    ret[key] = value.serialise()
                else:
                    ret[key] = value

        return ret

    def add_attribute(self, name, value) -> None:
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
                setattr(self, name, value)
            else:
                raise AttributeError("%s attribute '%s' expects %s, not %s" % (
                    self.__class__.__name__,
                    name,
                    self.properties_types[name].__name__,
                    value.__class__.__name__
                ))
        else:
            if not self._additional:
                raise AttributeError(
                    "Unspecified Attribute '%s' not allowed in '%s' object" %
                    (name, self.__class__.__name__))
            else:
                self.additional_data_types[name] = value.__class__
                setattr(self, name, value)
