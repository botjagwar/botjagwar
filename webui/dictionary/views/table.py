from django.template import Template, Context

from .base import View
from .columns import TableColumnView


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
        :param data: list of object representing a serialised object
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
