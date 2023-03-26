import requests

from api.config import BotjagwarConfig


class NllbTranslation(object):
    endpoint = '/translate'
    backend = BotjagwarConfig().get('backend_address', 'nllb')

    def __init__(self, source='en_Latn', target='plt_Latn'):
        self.source = source
        self.target = target

    def get_translation(self, sentence: str):
        data = {
            'text': sentence
        }
        response = requests.post(self.backend + f"/translate", json=data)
        return response.json()['translated']
