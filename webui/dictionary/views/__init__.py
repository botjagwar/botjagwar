from django.http import HttpResponse
from django import forms

from .base import PageView
from .base import SectionView
from .table import LinkedTableColumnView
from .table import CommaSeparatedListTableColumnView
from .table import TableView
from .table import TableColumnView

import requests
import json


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
    lang = request.GET.get('lang', '')
    req = requests.get('http://127.0.0.1:8001/dictionary/%s' % lang).text

    page = PageView()
    table_section = SectionView('Word list for language %s' % lang)

    table_view = TableView()
    table_view.set_data(json.loads(req))

    linked_word_view = LinkedTableColumnView('Word', 'word')
    linked_word_view.set_link_pattern("/word/%(id)d")
    table_view.add_column(linked_word_view)

    table_view.add_column(TableColumnView('Language', 'language'))

    definitions_viewer = CommaSeparatedListTableColumnView('Definition', 'definitions')
    definitions_viewer.select_displayed_data('definition')
    table_view.add_column(definitions_viewer)

    table_section.add_view(table_view)
    page.add_section(table_section)
    rendered_view = page.render()

    return HttpResponse(rendered_view)