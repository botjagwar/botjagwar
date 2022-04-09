from . import Builder


class JSONBuilderError(Exception): pass


class JSONBuilder(Builder):
    def __init__(self):
        super(JSONBuilder, self).__init__()
        self.json_node = {}

    def serialise(self) -> dict:
        main_node = {}

        # Subnodes
        for json_node_name, attribute_name in self.mapped_variables:
            element = {}
            try:
                attribute_value = getattr(self, attribute_name)
            except AttributeError as e:
                raise JSONBuilderError("JSON node '%s' in %s class is mapped to non-existing attribute '%s'" % (
                    json_node_name, self.__class__.__name__, attribute_name))

            if isinstance(attribute_value, list):
                element[attribute_name] = []
                for e in attribute_value:
                    if isinstance(e, Builder):
                        element[attribute_name].append(e.serialise())
                    else:
                        raise JSONBuilderError("'%s' is not a serialisable element" % e.__class__)
            elif isinstance(attribute_value, Builder):
                main_node[attribute_name] = attribute_value.serialise()
                continue
            elif isinstance(attribute_value, str):
                element[attribute_name] = attribute_value
            elif isinstance(attribute_value, int):
               element[attribute_name] = str(attribute_value)
            else:
                raise JSONBuilderError("'%s' is not a serialisable element" % attribute_value.__class__)

            if attribute_name in main_node:
                if isinstance(main_node[attribute_name], list):
                    main_node[attribute_name].append(element)
                else:
                    main_node[attribute_name] = [element]

            if len(main_node[attribute_name]) == 1:
                main_node[attribute_name] = main_node[attribute_name][0]

        return main_node

