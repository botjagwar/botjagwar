import requests

from api.config import BotjagwarConfig


class OpenMtTranslation(object):
    endpoint = '/translate'
    backend = BotjagwarConfig().get('backend_address', 'openmt')

    def __init__(self, source='en', target='mg'):
        self.source = source
        self.target = target

    def get_translation(self, sentence: str):
        data = {
            'text': sentence
        }
        response = requests.post(self.backend + f"/translate/{self.source}/{self.target}", json=data)
        return response.json()['text']
