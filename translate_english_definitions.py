import pywikibot
import requests

from api.model.word import Entry
from api.translation_v2.core import Translation


class DefinitionTranslationError(Exception):
    pass


class DefinitionTranslation(object):
    def __init__(self):
        self.botjagwar_frontend_url = '192.168.10.100:8080'
        self.translation_server = 'localhost:8003'
        self.definition_language = 'en'
        self.language = 'en'

        self._words_to_link = set()

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

    def import_into_additional_data(self):
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

    def check_translation_quality(self):
        """
        Check whether translation has translated all the key words (adjectives, nouns) of the
        original text, or if some words have been skipped; and check if resulting translation words are
        present in the dictionary of either dictionary. If a word cannot be traced or referenced in the dictionary,
        the check fails.
        :return:
        """
        pass

    def get_word_info_with_openmt_additional_data(self, items_per_page):
        url = f'http://{self.botjagwar_frontend_url}/api/additional_word_information'
        for page_number in range(100):
            pages = requests.get(url, params={
                'limit': items_per_page,
                'offset': items_per_page * page_number,
                'type': f'eq.openmt_translation',
            })
            if pages.status_code != 200:
                print(pages.json())
                raise DefinitionTranslationError(pages.text)

            pages_as_json = pages.json()
            for page in pages_as_json:
                yield page

    def get_word_by_id(self, word_id):
        url = f'http://{self.botjagwar_frontend_url}/api/unaggregated_dictionary'
        pages = requests.get(url, params={
            'word_id': f'eq.{word_id}',
        })
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        return pages.json()[0]

    def get_definitions(self, word_id):
        url = f'http://{self.botjagwar_frontend_url}/api/unaggregated_dictionary'
        pages = requests.get(url, params={
            'word_id': f'eq.{word_id}',
            'definition_language': f'eq.{self.definition_language}',
        })
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        return [line['definition'] for line in pages.json()]

    def mark_definition(self, word_id, mark_as='done'):
        url = f'http://{self.botjagwar_frontend_url}/api/additional_word_information'
        pages = requests.patch(url, params={
            'word_id': f'eq.{word_id}',
            'type': f'eq.openmt_translation',
        }, json={
            'type': f'openmt_translation/{mark_as}'
        })
        if pages.status_code != 204:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

    def get_translated_definitions(self, word_id):
        url = f'http://{self.botjagwar_frontend_url}/api/additional_word_information'
        pages = requests.get(url, params={
            'word_id': f'eq.{word_id}',
            'type': f'eq.openmt_translation',
        })
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        return [line['information'] for line in pages.json()]

    @property
    def malagasy_words_to_link(self):
        if self._words_to_link:
            return self._words_to_link
        else:
            url = f'http://{self.botjagwar_frontend_url}/api/word'
            pages = requests.get(url, params={
                'language': f'eq.mg',
                'part_of_speech': f'in.(ana,mat,mpam)',
                'select': f'word',
            })
            if pages.status_code != 200:
                raise DefinitionTranslationError(pages.text)
            else:
                self._words_to_link = {p['word'] for p in pages.json() if len(p['word']) > 4}
                return self._words_to_link


    def publish_translated_definition(self):
        """
        Publish the translated definition on the target wiki.
        :return:
        """
        definitions = []
        translation = Translation()
        translation.output.wikipage_renderer.pages_to_link = self.malagasy_words_to_link

        for word_additional_data_info in self.get_word_info_with_openmt_additional_data(100):
            word_info = self.get_word_by_id(word_additional_data_info['word_id'])
            word_id = word_info['word_id']
            word = word_info['word']
            part_of_speech = word_info['part_of_speech']
            definitions = self.get_definitions(word_id)
            translated_definitions = self.get_translated_definitions(word_id)
            print(f'{word} ({word_id}) ->', definitions, translated_definitions)
            entry = Entry(
                entry=word,
                part_of_speech=part_of_speech,
                language=self.language,
                definitions=translated_definitions
            )
            response = pywikibot.input('Accept and upload? (y/n)')
            if response.strip() == 'y':
                translation.publish_to_wiktionary(entry.entry, [entry])
                translation._save_translation_from_page([entry])
                self.mark_definition(word_id, 'done')
            elif response.strip() == 'n':
                self.mark_definition(word_id, 'rejected')
            else:
                continue
            # translation._save_translation_from_page(entries)


if __name__ == '__main__':
    bot = DefinitionTranslation()
    bot.publish_translated_definition()
