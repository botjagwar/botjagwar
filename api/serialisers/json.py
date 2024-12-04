from . import Builder


class JSONBuilderError(Exception):
    pass


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
                raise JSONBuilderError(
                    f"JSON node '{json_node_name}' in {self.__class__.__name__} class is mapped to non-existing attribute '{attribute_name}'"
                ) from e

            if isinstance(attribute_value, Builder):
                main_node[json_node_name] = attribute_value.serialise()
                continue
            if attribute_value.__class__ in (dict, str) or type(
                attribute_value
            ) in (float, int):
                main_node[json_node_name] = attribute_value
            elif attribute_value is None:
                main_node[json_node_name] = None
            elif hasattr(attribute_value, "__iter__"):
                print(json_node_name, "=", attribute_value)
                main_node[json_node_name] = []
                for e in attribute_value:
                    if isinstance(e, Builder):
                        main_node[json_node_name].append(e.serialise())
                    elif hasattr(e, "serialise"):
                        try:
                            serialised = e.serialise()
                        except Exception as error:
                            raise JSONBuilderError(
                                f"Error when trying to serialise '{e.__class__}': {e.message}"
                            ) from error
                        else:
                            if isinstance(serialised, dict):
                                main_node[json_node_name].append(serialised)
                            else:
                                raise JSONBuilderError(
                                    f"'{e.__class__.__name__}' has serialise() method,"
                                    f" but return type of such method is invalid."
                                    f" dict is expected. Got {serialised.__class__.__name__}"
                                )
                    else:
                        main_node[json_node_name].append(e)
            else:
                raise JSONBuilderError(
                    f"'{attribute_value.__class__}' is not a serialisable element"
                )

        return main_node
