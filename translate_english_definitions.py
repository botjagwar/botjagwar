import requests


class DefinitionTranslationError(Exception):
    pass


class DefinitionTranslation(object):
    def __init__(self):
        self.botjagwar_frontend_url = '192.168.10.100:8080'
        self.translation_server = 'localhost:8003'
        self.definition_language = 'en'
        self.language = 'en'

    def get_words(self, language='en', page_number=1, words_per_page=10000):
        url = f'http://{self.botjagwar_frontend_url}/api/unaggregated_dictionary'

        pages = requests.get(url, params={
            'limit': words_per_page,
            'offset': words_per_page * page_number,
            'definition_language': f'eq.{self.definition_language}',
            'language': f'eq.{self.language}',
            'order': 'word_id.desc'
        })
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        pages_as_json = pages.json()
        for page in pages_as_json:
            yield page

    def openmt_get_translation(self, text):
        url = f'http://{self.translation_server}/translate/{self.definition_language}/mg'
        json = {
            'text': text
        }
        request = requests.post(url, json=json)
        if request.status_code != 200:
            raise DefinitionTranslationError('Unknown error: ' + request.text)
        else:
            return request.json()['text']

    def add_additional_data(self, word_id, type, information):
        url = f'http://{self.botjagwar_frontend_url}/api/additional_word_information'
        json = {
            'word_id': word_id,
            'type': type,
            'information': information
        }
        print(json)
        request = requests.post(url, json=json)
        if 400 <= request.status_code <= 599:
            raise DefinitionTranslationError('Unknown error: ' + request.text)

    def run(self):
        for page in range(70):
            for word in self.get_words('en', page):
                word_id = word['word_id']
                definition = word['definition']
                try:
                    self.add_additional_data(
                        word_id,
                        'openmt_translation',
                        self.openmt_get_translation(definition)
                    )
                except Exception:
                    continue


if __name__ == '__main__':
    bot = DefinitionTranslation()
    bot.run()
