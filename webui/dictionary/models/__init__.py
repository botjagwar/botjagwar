from pprint import pprint

import requests
from django.forms import fields
from django.forms.forms import Form

from .constants import PART_OF_SPEECH_CHOICES
from .form_utils import fetch_languages

BACKEND_ADDRESS_HEADER = 'http://localhost:8001'


class DefinitionEditForm(Form):
    definition_language = fetch_languages('Language')
    definition = fields.CharField(label='Definition', )
    definition_id = fields.CharField(label='Definition ID')

    def __init__(self, request_context=None, *args, **kwargs):
        super(DefinitionEditForm, self).__init__(request_context, *args, **kwargs)
        self.items['definition_id'] = kwargs.pop('definition_id')

    @staticmethod
    def format_to_backend_data(form_data):
        pprint(form_data)
        return {
            'definition_id': form_data['definition_id'],
            'type': 'Definition',
            'definition': form_data['definition'],
            'definition_language': form_data['definition_language']
        }

    def save(self):
        form_data = self.cleaned_data
        json_data = self.format_to_backend_data(form_data)
        # Fixme: Use config instead of hardcoded backend address
        req = requests.put(
            BACKEND_ADDRESS_HEADER + '/definition/%(definition_language)s' % form_data,
            json=json_data
        )
        if req.status_code != 200:
            raise Exception("Error: Backend answered: %s" % req.text)


class WordEditionForm(Form):
    word = fields.CharField(label='Word', max_length=200)
    part_of_speech = fields.ChoiceField(label="Part of speech", choices=PART_OF_SPEECH_CHOICES)
    language = fetch_languages('Language')
    definition = fields.CharField(label="Definition")
    definition_language = fetch_languages('Definition language')

    def __init__(self, request_context=None, *args, **kwargs):
        super(WordEditionForm, self).__init__(request_context, *args, **kwargs)

    @staticmethod
    def format_to_backend_data(form_data):
        definitions = [{
            'type': 'Definition',
            'definition': form_data['definition'],
            'definition_language': form_data['definition_language']
        }]
        json_data = {
            'type': 'Word',
            'word': form_data['word'],
            'part_of_speech': form_data['part_of_speech'],
            'language': form_data['language'],
            'definitions': definitions
        }
        return json_data

    def save(self):
        form_data = self.cleaned_data
        json_data = self.format_to_backend_data(form_data)
        req = requests.post(BACKEND_ADDRESS_HEADER + '/entry/%(language)s/create' % form_data, json=json_data)
        if req.status_code != 200:
            raise Exception("Error: Backend answered: %s" % req.text)