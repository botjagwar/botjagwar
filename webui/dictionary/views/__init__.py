from django.http import HttpResponse
from django import forms

from .base import PageView
from .base import SectionView
from .base import StringListView

from .table import ActionColumnView
from .table import LinkedTableColumnView
from .table import CommaSeparatedListTableColumnView
from .table import TableView
from .table import TableColumnView

import requests
import json

SERVER = '127.0.0.1:8001'


class WordEditForm(forms.Form):
    word = forms.CharField(label='Word', max_length=100)
    language = forms.CharField(label='Language', max_length=6)
    part_of_speech = forms.CharField(label='Part of speech', max_length=5)


def index(request):
    print(request)
    return HttpResponse('INDEKS')


def render_definitions(definitions):
    return ', '.join([definition['definition'] for definition in definitions])


def render_word(objekt):
    ret_str = "<a href=/word/%(id)s>%(word)s</a>" % objekt
    return ret_str


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

    pos_section.add_view(definitions_list_view)

    word_section.add_view(pos_section)
    page.add_section(word_section)

    return HttpResponse(page.render())


def word_list_view(request):
    lang = request.GET.get('lang', '')
    server = request.GET.get('server', SERVER)
    req = requests.get('http://%s/dictionary/%s' % (server, lang)).text

    page = PageView()
    table_section = SectionView('Word list for language %s' % lang)

    table_view = TableView()
    table_view.set_data(json.loads(req))

    linked_word_view = LinkedTableColumnView('Word', 'word')
    linked_word_view.set_link_pattern("/word?id=%(id)d")

    table_view.add_column(linked_word_view)
    table_view.add_column(TableColumnView('Language', 'language'))

    definitions_viewer = CommaSeparatedListTableColumnView('Definition', 'definitions')
    definitions_viewer.select_displayed_data('definition')
    table_view.add_column(definitions_viewer)

    delete_word_view = ActionColumnView('Delete', 'delete')
    delete_word_view.set_link_pattern("/delete_word?id=%(id)d")
    table_view.add_column(delete_word_view)

    table_section.add_view(table_view)
    page.add_section(table_section)
    rendered_view = page.render()

    return HttpResponse(rendered_view)


def delete_word(request):
    id_ = int(request.GET.get('id', '0'))
    requests.delete('http://' + SERVER + '/entry/%d/delete' % id_)

    return HttpResponse('OK')
