from django.template import Template, Context
from .base import View


class TableColumnView(View):
    """
    Display object data in table columns
    """
    def __init__(self, name, object_attribute_name):
        super(View, self).__init__()
        self.name = name
        self.object_attribute_name = object_attribute_name

    def render(self):
        try:
            return self.data[self.object_attribute_name]
        except KeyError as err:
            possible_keys = ', '.join(self.data.keys())
            raise KeyError('Unable to fetch value from key. Possible values are: %s' % possible_keys) from err


class LinkedTableColumnView(TableColumnView):
    """
    Manage text with link(s) in a table cell
    """
    def __init__(self, name, object_attribute_name):
        super(LinkedTableColumnView, self).__init__(name, object_attribute_name)
        self.link_pattern = None

    def set_link_pattern(self, link_dictionary_patterns):
        """
        :param link_dictionary_patterns:
        :return:
        """
        self.link_pattern = link_dictionary_patterns

    def render(self):
        template = Template("<a href=\"{{ link }}\">{{ text }}</a>")
        try:
            text = self.data[self.object_attribute_name]
        except KeyError as err:
            possible_keys = ', '.join(self.data.keys())
            raise KeyError('Unable to fetch value from key. Possible values are: %s' % possible_keys) from err
        else:
            return template.render(Context({
                'link': self.link_pattern % self.data,
                'text': text
            }))


class ActionColumnView(LinkedTableColumnView):
    """
    Column view with no data to show, but rather with actions to do on data such as edit or delete
    """
    def __init__(self, name, label):
        super(LinkedTableColumnView, self).__init__(name, label)
        self.link_pattern = None
        self.label = label

    def render(self):
        template = Template("<a href=\"{{ link }}\">{{ text }}</a>")
        return template.render(Context({
            'link': self.link_pattern % self.data,
            'text': self.label
        }))


class CommaSeparatedListTableColumnView(TableColumnView):
    """
    Displays a comma-separated list in a table column. That list contains one value of the list of objects
    """
    def select_displayed_data(self, key):
        self.displayed_data = key

    def render(self):
        return ", ".join(datum[self.displayed_data] for datum in self.data[self.object_attribute_name])
