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

    def serialise(self) -> Element:
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
            elif attribute_value is None:
                element.text = ""
            else:
                raise XMLBuilderError("'%s' is not a serialisable element" % attribute_value.__class__)

            main_node.append(element)

        return main_node
