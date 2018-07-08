import json

import requests
from django.http import HttpResponse

from .base import PageView
from .base import SectionView
from .base import StringListView
from .columns import ActionColumnView
from .columns import CommaSeparatedListTableColumnView
from .columns import LinkedTableColumnView
from .form import FormView
from .table import TableColumnView
from .table import TableView
from ..models import WordEditionForm

SERVER = 'localhost:8001'


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
    definitions_viewer.set_element_link_pattern('/definition?id=%(id)d')
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


def word_edit(request):
    if request.method == 'POST':
        form = WordEditionForm(request.POST)
        if form.is_valid():
            form.save()
        # if a GET (or any other method) we'll create a blank form
    else:
        form = WordEditionForm()

    page = PageView("Editing")
    form_view = FormView(form, 'word_edit', request)
    edit_section = SectionView("Word")
    edit_section.add_view(form_view)
    page.add_section(edit_section)

    return HttpResponse(page.render())