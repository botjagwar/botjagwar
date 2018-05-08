import requests
from django.forms import fields


def fetch_languages(label):
    language_req = requests.get('http://localhost:8003/languages')
    choices_data = language_req.json()
    choices = [(language['code'],
                language['english_name']
                if language['english_name'] is not None
                else language['code']) for language in choices_data]
    choices.sort()
    return fields.ChoiceField(label=label, choices=tuple(choices))
