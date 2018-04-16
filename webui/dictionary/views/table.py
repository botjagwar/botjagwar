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


class TableView(View):
    """
    Display a list of JSON-serialised data of the same type in a table
    """
    def __init__(self):
        super(TableView, self).__init__()
        self.columns = []

    def set_data(self, data: list):
        """
        Set the data to display in the table
        :param data: list of dictionaries representing a serialised object
        :return:
        """
        self.data = data

    def add_column(self, column: TableColumnView):
        """
        Add a column to the table
        :param column: a TableColumnView class
        :return:
        """
        self.columns.append(column)

    def render(self):
        """
        Render the table
        :return: A string containing the HTML table
        """
        head_template = Template('<th>{{ name }}<th>\n')
        row_template = Template('<td>{{ data }}<td>\n')
        table = "<table id='%s_table' class='table'>\n" % (self.__class__.__name__)

        # Rendering head
        table += '<tr id="%s_head">\n' % (self.__class__.__name__)
        for column in self.columns:
            table += head_template.render(Context({'name': column.name}))

        table += '</tr>\n'

        # Rendering rows
        i = 0
        for datum in self.data:
            table += '<tr id="%s_item_%d">\n' % (self.__class__.__name__, i)
            for column in self.columns:
                column.set_data(datum)
                table += row_template.render(Context({'data': column.render()}))

            table += '</tr>\n'
            i += 1

        table += "</table>\n"

        return table
