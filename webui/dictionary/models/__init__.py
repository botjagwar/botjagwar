import requests

from django.forms.forms import Form
from django.forms import fields

from .constants import PART_OF_SPEECH_CHOICES
from .form_utils import fetch_languages

from pprint import pprint


class WordEditionForm(Form):
    word = fields.CharField(label='Word', max_length=200)
    part_of_speech = fields.ChoiceField(label="Part of speech", choices=PART_OF_SPEECH_CHOICES)
    language = fetch_languages('Language')
    definition = fields.CharField(label="Definition")
    definition_language = fetch_languages('Definition language')

    def __init__(self, *args, **kwargs):
        super(WordEditionForm, self).__init__(*args, **kwargs)

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
        pprint(form_data)
        json_data = self.format_to_backend_data(form_data)
        pprint(json_data)
        req = requests.post('http://localhost:8001/entry/%(language)s/create' % form_data, json=json_data)
        if req.status_code != 200:
            raise Exception("Error: Backend answered: %s" % req.text)