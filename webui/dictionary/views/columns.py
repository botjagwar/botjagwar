from django.template import Template, Context

from .base import View


class TableColumnView(View):
    """
    Display object data in table columns.
    """
    def __init__(self, name, object_attribute_name):
        """
        :param name: Name of the column as displayed in the header
        :param object_attribute_name: JSON element key to bind that column name to
        """
        super(View, self).__init__()
        self.name = name
        self.object_attribute_name = object_attribute_name

    def render(self):
        try:
            return self.data[self.object_attribute_name]
        except KeyError as err:
            possible_keys = ', '.join(self.data.keys())
            msg = 'Unable to fetch value from key "%s".' % self.object_attribute_name
            msg += ' Possible values are: %s' % possible_keys
            raise KeyError(msg) from err


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
            msg = 'Unable to fetch value from key "%s".' % self.object_attribute_name
            msg += ' Possible values are: %s' % possible_keys

            raise KeyError(msg) from err
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

    def set_request_context(self, context):
        self.request_context = context

    def render(self):
        template = Template("<a href=\"{{ link }}\">{{ text }}</a>")
        return template.render(Context({
            'link': self.link_pattern % self.data,
            'text': self.label
        }))


class EditColumnView(ActionColumnView):
    def __init__(self):
        super(EditColumnView, self).__init__('edit', 'id')

    def render(self):
        self.link_pattern = '/dictionary/%(type)s/edit?id=%(id)d'
        template = Template("<a href=\"{{ link }}\">{{ text }}</a>")
        return template.render(Context({
            'link': self.link_pattern % self.data,
            'text': 'edit'
        }))


class DissociateColumnView(ActionColumnView):
    def __init__(self):
        super(DissociateColumnView, self).__init__('dissociate', 'id')

    def render(self):
        self.link_pattern = '/dictionary/%(type)s/dissociate?did=%(id)d'
        link = self.link_pattern % self.data
        link += '&wid=%d' % int(self.request_context.GET.get('id', ''))
        template = Template("<a href=\"{{ link }}\">{{ text }}</a>")
        print(self.data)
        return template.render(Context({
            'link': link,
            'text': 'dissociate'
        }))


class CommaSeparatedListTableColumnView(TableColumnView):
    """
    Displays a comma-separated list in a table column. That list contains one value of the list of objects
    """
    link_pattern = None

    def select_displayed_data(self, key):
        self.displayed_data = key

    def set_element_link_pattern(self, pattern):
        self.link_pattern = pattern

    def apply_link_pattern(self, element):
        link = self.link_pattern % element
        template = Template("<a href=\"{{ link }}\">{{ text }}</a>")
        if self.link_pattern:
            return template.render(Context({
                'link': link,
                'text': element[self.displayed_data]
            }))
        else:
            return element[self.displayed_data]

    def render(self):
        out_str = ", ".join(self.apply_link_pattern(datum) for datum in self.data[self.object_attribute_name])
        return Template("{{text|safe}}").render(Context({'text': out_str}))
