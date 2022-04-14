from xml.etree.ElementTree import Element

from . import Builder


class XMLBuilderError(Exception): pass


class XMLBuilder(object):
    """
    Generic JSON object serialiser.
    """
    def __init__(self):
        # XML node name
        self.xml_node = ""

        # Variables that will be mapped to an XML node. List of tuples. Variables will appear in the same order
        #  as the node order.
        self.mapped_variables = []

        # XML node
        self._xml_root = Element(self.xml_node)

    def serialise_dict(self, attribute_value) -> Element:
        dictionary = Element('KeyValuePairs')
        for k, v in attribute_value.items():
            v = v[0]
            kvp_element = Element('KeyValuePair')

            kvp_key = Element('Key')
            if isinstance(k, Builder):
                kvp_key.append(k.serialise())
                continue
            elif k.__class__ in (int, str):
                kvp_key.text = str(k)
            elif isinstance(k, dict):
                kvp_key.append(self.serialise_dict(k))

            kvp_value = Element('Value')
            if isinstance(v, Builder):
                kvp_value.append(v.serialise())
                continue
            elif v.__class__ in (int, str):
                kvp_value.text = str(v)
            # elif isinstance(v, list):
            #     kvp_value.append(self.serialise_list(kvp_value, v))
            elif isinstance(v, dict):
                kvp_value.append(self.serialise_dict(v))

            kvp_element.append(kvp_key)
            kvp_element.append(kvp_value)
            dictionary.append(kvp_element)

        return dictionary

    def serialise(self) -> dict:
        # Main node
        main_node = Element(self.xml_node)

        # Subnodes
        for xml_node_name, attribute_name in self.mapped_variables:
            element = Element(xml_node_name)
            try:
                attribute_value = getattr(self, attribute_name)
            except AttributeError as e:
                raise XMLBuilderError("XML node '%s' in %s class is mapped to non-existing attribute '%s'" % (
                    xml_node_name, self.__class__.__name__, attribute_name))

            if isinstance(attribute_value, list):
                for e in attribute_value:
                    if isinstance(e, Builder):
                        element.append(e.serialise())
                    else:
                        raise XMLBuilderError("'%s' is not a serialisable element" % e.__class__)
            elif isinstance(attribute_value, Builder):
                main_node.append(attribute_value.serialise())
                continue
            elif isinstance(attribute_value, str):
                element.text = attribute_value
            elif isinstance(attribute_value, int):
                element.text = str(attribute_value)
            elif isinstance(attribute_value, dict):
                element.append(self.serialise_dict(attribute_value))

            elif attribute_value is None:
                element.text = ""
            else:
                raise XMLBuilderError("'%s' is not a serialisable element" % attribute_value.__class__)

            main_node.append(element)

        return main_node
