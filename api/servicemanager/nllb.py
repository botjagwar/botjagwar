import requests

from api.config import BotjagwarConfig

CONFIG = BotjagwarConfig()


class DefinitionTranslationError(Exception):
    pass


class NllbDefinitionTranslation(object):
    def __init__(self):
        self.translation_server = CONFIG.get('backend_address', 'nllb')
        # Translator parameters
        self.translator_definition_language = 'en_Latn'
        self.translator_target_language = 'plt_Latn'

    def get_translation(self, sentence: str):
        url = f'http://{self.translation_server}/translate/' \
              f'{self.translator_definition_language}/' \
              f'{self.translator_target_language}'
        json = {
            'text': sentence
        }
        print(url, json)
        request = requests.get(url, params=json)
        if request.status_code != 200:
            raise DefinitionTranslationError('Unknown error: ' + request.text)
        else:
            return request.json()['translated']
