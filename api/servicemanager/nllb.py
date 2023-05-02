import requests

from api.config import BotjagwarConfig

CONFIG = BotjagwarConfig()
NLLB_CODE = {
    'en': 'en_Latn',
    'fr': 'fr_Latn',
    'mg': 'plt_Latn',
    'de': 'de_Latn',
    'ru': 'ru_Cyrl',
    'uk': 'uk_Cyrl',
    'nl': 'nl_Latn',
    'no': 'no_Latn',
    'sv': 'sv_Latn',
    'fi': 'fi_Latn',
    'da': 'da_Latn',
    'zh': 'zh_Hans',
    'cmn': 'cmn_Hans',
    'vi': 'vi_Latn',
    'id': 'id_Latn',
    'ms': 'ms_Latn',
    'fil': 'fil_Latn',
    'ko': 'ko_Kore',
}


class DefinitionTranslationError(Exception):
    pass


class NllbDefinitionTranslation(object):
    def __init__(self, target_language, source_language='en'):
        """
        Translate using a NLLB service spun up on another server.
        :param target_language:
        :param source_language:
        """
        self.translation_server = CONFIG.get('backend_address', 'nllb')

        # Translator parameters
        self.source_language = NLLB_CODE.get(source_language, NLLB_CODE['en'])
        self.target_language = NLLB_CODE.get(target_language, NLLB_CODE['mg'])

    def get_translation(self, sentence: str):
        # fix weird behaviour where original text can be kept
        sentence = sentence.replace('’', "'")
        sentence = sentence.replace(']', '')
        sentence = sentence.replace('[', '')

        print(f"Translating sentence: {sentence}")
        url = f'http://{self.translation_server}/translate/' \
              f'{self.source_language}/' \
              f'{self.target_language}'
        json = {
            'text': sentence
        }
        request = requests.get(url, params=json)
        if request.status_code != 200:
            raise DefinitionTranslationError('Unknown error: ' + request.text)
        else:
            translated = request.json()['translated']
            if translated.startswith('(') and translated.endswith(')'):
                translated = translated[1:-1]
            translated = translated.replace(sentence, '')  # fix weird behaviour where original text can be kept...
            print('TRANSLATED:::' + translated)
            return translated
