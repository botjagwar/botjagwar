import requests
from django.http import HttpResponse

from ..models import WordEditionForm, DefinitionEditForm
from ..views import SERVER
from ..views.base import PageView
from ..views.base import SectionView
from ..views.form import FormView


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


def definition_delete(request):
    id_ = int(request.GET.get('id', '0'))
    requests.delete('http://' + SERVER + '/entry/%d/delete' % id_)

    return HttpResponse('OK')


def definition_edit(request):
    if request.method == 'POST':
        form = DefinitionEditForm(request.POST)
        if form.is_valid():
            form.save()
    elif request.method == 'GET':
        req = requests.get('http://%s/definition/%d' % (SERVER, int(request.GET.get('id'))))
        definition_object = req.json()[0]
        initial_values = {
            'definition_language': definition_object['language'],
            'definition' : definition_object['definition']
        }
        print(initial_values, definition_object)
        form = DefinitionEditForm(initial=initial_values)
    else:
        form = DefinitionEditForm()

    page = PageView("Editing")
    form_view = FormView(form, 'definition_edit', request)
    edit_section = SectionView("Definition")
    edit_section.add_view(form_view)
    page.add_section(edit_section)

    return HttpResponse(page.render())