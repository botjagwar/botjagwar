import json

import requests
from django.http import HttpResponse

from .. import SERVER
from ..base import PageView
from ..base import SectionView
from ..columns import ActionColumnView, EditColumnView, DissociateColumnView
from ..columns import CommaSeparatedListTableColumnView
from ..columns import LinkedTableColumnView
from ..table import TableColumnView
from ..table import TableView


def render_word(objekt):
    ret_str = "<a href=/dictionary/word/%(id)s>%(word)s</a>" % objekt
    return ret_str


def languages_view(request):
    server = request.GET.get('server', SERVER)
    language_list = requests.get('http://%s/languages/list' % server).text

    page = PageView('List of languages')
    language_list_view = TableView()
    language_link = LinkedTableColumnView('Language', 'language')
    language_link.set_link_pattern('/dictionary/Word/list?lang=%(language)s')
    language_list_view.set_data(json.loads(language_list))
    language_list_view.add_column(language_link)
    language_list_view.add_column(TableColumnView('Number of entries', 'entries'))

    table_section = SectionView('List of languages')
    table_section.add_view(language_list_view)
    page.add_section(table_section)
    return HttpResponse(page.render())


def word_view(request):
    id_ = request.GET.get('id', '')
    server = request.GET.get('server', SERVER)
    req = requests.get('http://%s/word/%s' % (server, id_)).text
    data = json.loads(req)

    page = PageView(data['word'])
    word_section = SectionView('%s' % data['word'])
    pos_section = SectionView('%s' % data['part_of_speech'])

    definitions_list_view = TableView()
    definitions_list_view.set_data(data['definitions'])
    definitions_list_view.add_column(TableColumnView('#', 'id'))
    definitions_list_view.add_column(TableColumnView('Definition', 'definition'))
    definitions_list_view.add_column(TableColumnView('Last modified', 'last_modified'))
    edit_column_view = EditColumnView()
    edit_column_view.set_request_context(request)
    definitions_list_view.add_column(edit_column_view)
    dissociate_column_view = DissociateColumnView()
    dissociate_column_view.set_request_context(request)
    definitions_list_view.add_column(dissociate_column_view)
    pos_section.add_view(definitions_list_view)

    word_section.add_view(pos_section)
    page.add_section(word_section)

    return HttpResponse(page.render())


def word_list_view(request):
    lang = request.GET.get('lang', '')
    server = request.GET.get('server', SERVER)
    req = requests.get('http://%s/dictionary/%s' % (server, lang)).text

    # Generate table and bind JSON data to columns
    table_view = TableView()
    table_view.set_data(json.loads(req))

    linked_word_view = LinkedTableColumnView('Word', 'word')
    linked_word_view.set_link_pattern("/dictionary/Word/view?id=%(id)d")
    definitions_viewer = CommaSeparatedListTableColumnView('Definition', 'definitions')
    definitions_viewer.select_displayed_data('definition')
    definitions_viewer.set_element_link_pattern('/dictionary/Definition/view?id=%(id)d')
    delete_word_view = ActionColumnView('Delete', 'delete')
    delete_word_view.set_link_pattern("/dictionary/Word/delete?id=%(id)d")

    #
    table_view.add_column(linked_word_view)
    table_view.add_column(TableColumnView('Language', 'language'))
    table_view.add_column(definitions_viewer)
    table_view.add_column(TableColumnView('Last modified', 'last_modified'))
    table_view.add_column(delete_word_view)

    # Generate page in which table included
    page = PageView()
    table_section = SectionView('Word list for language %s' % lang)
    table_section.add_view(table_view)
    page.add_section(table_section)

    # Render!
    rendered_view = page.render()
    return HttpResponse(rendered_view)
