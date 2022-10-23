import csv
import os.path

import pywikibot
import requests

from api.model.word import Entry
from api.translation_v2.core import Translation


class DefinitionTranslationError(Exception):
    pass


class BatchCreationError(DefinitionTranslationError):
    pass


class DefinitionTranslation(object):
    def __init__(self):
        self.postgrest_url = '192.168.10.100:8080/api'
        self.botjagwar_frontend_url = '192.168.10.100:8080'
        self.translation_server = 'localhost:8003'
        self.definition_language = 'fr'
        self.language = 'fr'

        self._words_to_link = set()
        self._wordlist = set()
        self._current_file_size = 0
        self._batch_file_counter = 1
        self._current_file = None

    def get_words(self, page_number=1, words_per_page=10000):
        url = f'http://{self.postgrest_url}/unaggregated_dictionary'

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
        url = f'http://{self.postgrest_url}/additional_word_information'
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
            for word in self.get_words(page):
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

    def get_word_info_with_openmt_additional_data(self, items_per_page, start_from_page=1):
        total_pages = 100
        url = f'http://{self.postgrest_url}/word_with_openmt_translation'
        for page_number in range(total_pages):
            print(f'(page {1+page_number}/{total_pages}) getting {items_per_page} pages from database...')
            pages = requests.get(url, params={
                'limit': items_per_page,
                'offset': (start_from_page + page_number) * items_per_page,
                'order': 'word_id',
                'language': 'eq.en',
            })
            if pages.status_code != 200:
                print(pages.json())
                raise DefinitionTranslationError(pages.text)

            pages_as_json = pages.json()
            for page in pages_as_json:
                yield page

    def get_word_by_id(self, word_id):
        url = f'http://{self.postgrest_url}/unaggregated_dictionary'
        pages = requests.get(url, params={
            'word_id': f'eq.{word_id}',
        })
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        return pages.json()[0]

    def get_definitions(self, word_id):
        url = f'http://{self.postgrest_url}/unaggregated_dictionary'
        pages = requests.get(url, params={
            'word_id': f'eq.{word_id}',
            'definition_language': f'eq.{self.definition_language}',
        })
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        return [line['definition'] for line in pages.json()]

    def mark_definition(self, word_id, mark_as='done'):
        url = f'http://{self.postgrest_url}/additional_word_information'
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
        url = f'http://{self.postgrest_url}/additional_word_information'
        pages = requests.get(url, params={
            'word_id': f'eq.{word_id}',
            'type': f'eq.openmt_translation',
        })
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        return [line['information'] for line in pages.json()]

    @property
    def wordlist(self):
        if self._wordlist:
            return self._wordlist
        else:
            print('Loading words')
            for word in open(f'user_data/list-{self.language}.txt', 'r'):
                word = word.strip()
                self._wordlist.add(word.lower())

            print('Loading complete!')
            return self._wordlist

    @property
    def malagasy_words_to_link(self):
        if self._words_to_link:
            return self._words_to_link
        else:
            print('Loading Malagasy words to link')
            url = f'http://{self.postgrest_url}/word'
            pages = requests.get(url, params={
                'language': f'eq.mg',
                'part_of_speech': f'in.(ana,mat,mpam)',
                'select': f'word',
            })
            if pages.status_code != 200:
                raise DefinitionTranslationError(pages.status_code)
            else:
                self._words_to_link = {p['word'] for p in pages.json() if len(p['word']) > 4}
                print(f'Loading complete! {len(self._words_to_link)} words loaded')
                return self._words_to_link

    def get_part_of_speech(self, word_id):
        url = f'http://{self.postgrest_url}/word'
        pages = requests.get(url, params={'id': f'eq.{word_id}'})
        if pages.status_code != 200:
            raise DefinitionTranslationError(pages.text)
        else:
            return pages.json()[0]['part_of_speech']

    def get_word_ids(self, words):
        words_as_csl = ','.join(words)
        url = f'http://{self.postgrest_url}/unaggregated_dictionary'
        pages = requests.get(url, params={
            'word': f'in.({words_as_csl})',
            'language': f'eq.fr',
        })
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        pages_as_json = pages.json()
        for page in pages_as_json:
            yield page

    def run(self, word_additional_data_info, counter=0):
        translation = Translation()
        translation.output.wikipage_renderer.pages_to_link = self.malagasy_words_to_link
        word = word_additional_data_info['word']
        word_id = word_additional_data_info['word_id']
        part_of_speech = word_additional_data_info['part_of_speech']
        definitions = self.get_definitions(word_id)
        translated_definitions = self.get_translated_definitions(word_id)
        print(f'{word} ({word_id}) ->', definitions, translated_definitions)
        entry = Entry(
            entry=word,
            part_of_speech=part_of_speech,
            language=self.language,
            definitions=translated_definitions
        )
        if not translated_definitions:
            return

        if translated_definitions and translated_definitions[0] == '.':
            return

        response = pywikibot.input(f'Entry # {counter + 1}: Accept and upload? (y/n)')
        if response.strip() == 'y':
            translation.publish_to_wiktionary(entry.entry, [entry])
            translation._save_translation_from_page([entry])
            self.mark_definition(word_id, 'done')
        elif response.strip() == 'n':
            self.mark_definition(word_id, 'rejected')
        else:
            return

    def publish_translated_definition(self):
        """
        Publish the translated definition on the target wiki.
        :return:
        """
        counter = 0
        words = []
        for word_list_element in self.wordlist:
            counter += 1
            words.append(word_list_element)
            if len(words) > 100:
                for word_additional_data_info in self.get_word_ids(words):
                    self.build_translation_batches(word_additional_data_info, counter)
                    # self.run(word_additional_data_info, counter)
                    # if not counter % 100:
                    #     print('You can take a break now!')
                words = []

    def build_translation_batches(self, word_additional_data_info, counter=0):
        translation = Translation()
        batch_folder = 'user_data/translation_batch'
        # translation.output.wikipage_renderer.pages_to_link = self.malagasy_words_to_link
        word = word_additional_data_info['word']
        word_id = word_additional_data_info['word_id']
        definitions = self.get_definitions(word_id)
        translated_definitions = self.get_translated_definitions(word_id)
        if not os.path.exists(batch_folder):
            os.mkdir(batch_folder)

        if os.path.exists(f'{batch_folder}/batch-{self._batch_file_counter}.csv'):
            self._current_file = open(f'{batch_folder}/batch-{self._batch_file_counter}.csv', 'a')

        if self._current_file is None:
            if self._current_file_size >= 5000:
                self._batch_file_counter += 1

            filename = f'{batch_folder}/batch-{self._batch_file_counter}.csv'
            self._current_file = open(filename, 'a')
        else:
            if self._current_file_size >= 5000:
                self._current_file_size = 0
                self._current_file.close()
                self._batch_file_counter += 1
                filename = f'{batch_folder}/batch-{self._batch_file_counter}.csv'
                self._current_file = open(filename, 'a')

        print(f'"{word}"/"{word_id}"/"{definitions}"/"{translated_definitions}"')
        if len(definitions) > 0:
            # if len(definitions) > 0 and len(translated_definitions) > 0:
            # if translated_definitions and translated_definitions[0] == '.':
            #     return

            # line = f'"{word}"/"{word_id}"/"{definitions[0]}"/"{translated_definitions[0]}"'
            line = f'"{word}"/"{word_id}"/"{definitions[0]}"'
            self._current_file.write(f'{line}\n')
            self._current_file_size += len(definitions[0])

    def import_translation_batch(self, batch_number=1):
        translation = Translation()
        batch_folder = 'user_data/translation_batch'
        # translation.output.wikipage_renderer.pages_to_link = self.malagasy_words_to_link
        if not os.path.exists(batch_folder):
            os.mkdir(batch_folder)

        if os.path.exists(f'{batch_folder}/batch-{batch_number}.csv'):
            self._current_file = open(f'{batch_folder}/batch-{batch_number}.csv', 'r')

        for row in csv.reader(self._current_file, delimiter=','):
            word, word_id, en_definition, mg_definition = row[:4]
            print(word, word_id, en_definition, mg_definition)
            if not mg_definition:
                continue
            part_of_speech = self.get_part_of_speech(int(word_id))
            entry = Entry(
                part_of_speech=part_of_speech,
                entry=word,
                definitions=[mg_definition.strip()],
                language='fr'
            )
            translation.publish_to_wiktionary(entry.entry, [entry])
            translation._save_translation_from_page([entry])


if __name__ == '__main__':
    import sys

    bot = DefinitionTranslation()
    bot.import_translation_batch(int(sys.argv[1]))
    # bot.publish_translated_definition()
