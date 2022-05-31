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
            try:
                attribute_value = getattr(self, attribute_name)
            except AttributeError as e:
                raise JSONBuilderError("JSON node '%s' in %s class is mapped to non-existing attribute '%s'" % (
                    json_node_name, self.__class__.__name__, attribute_name))

            if isinstance(attribute_value, Builder):
                main_node[json_node_name] = attribute_value.serialise()
                continue
            elif type(attribute_value) in (dict, str):
                main_node[json_node_name] = attribute_value
            elif type(attribute_value) in (float, int):
                main_node[json_node_name] = attribute_value
            elif hasattr(attribute_value, '__iter__'):
                print(json_node_name, '=', attribute_value)
                main_node[json_node_name] = []
                for e in attribute_value:
                    if isinstance(e, Builder):
                        main_node[json_node_name].append(e.serialise())
                    else:
                        if hasattr(e, 'serialise'):
                            try:
                                serialised = e.serialise()
                            except Exception as error:
                                raise JSONBuilderError(
                                    f"Error when trying to serialise '{e.__class__}': {e.message}"
                                ) from error
                            else:
                                if not isinstance(serialised, dict):
                                    raise JSONBuilderError(
                                        f"'{e.__class__.__name__}' has serialise() method,"
                                        f" but return type of such method is invalid."
                                        f" dict is expected. Got {serialised.__class__.__name__}"
                                    )
                                main_node[json_node_name].append(serialised)
                        else:
                            raise JSONBuilderError("'%s' is not a serialisable element" % e.__class__)
            else:
                raise JSONBuilderError("'%s' is not a serialisable element" % attribute_value.__class__)

            try:
                if len(main_node[json_node_name]) == 1:
                    main_node[json_node_name] = main_node[json_node_name][0]
            except Exception:
                print(main_node)

        return main_node
