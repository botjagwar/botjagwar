import csv
import os.path
from random import randint

import requests

import api.config
from api.entryprocessor.wiki.en import ENWiktionaryProcessor
from api.model.word import Entry
from api.translation_v2.core import Translation

CONFIG = api.config.BotjagwarConfig()


class PgrestServer:
    @property
    def server(self):
        port = randint(8100, 8108)
        return f'http://localhost:{port}'


def fetch_word(word, language, part_of_speech):
    dict_get_data = {
        'word': f'eq.{word}',
        'language': f'eq.{language}',
        'part_of_speech': f'eq.{part_of_speech}'
    }

    resp = requests.get(PgrestServer().server + '/word', params=dict_get_data)
    data = resp.json()
    if not (400 <= resp.status_code < 600):
        if data:
            return data[0]


class DefinitionTranslationError(Exception):
    pass


class BatchCreationError(DefinitionTranslationError):
    pass


class DefinitionTranslation(object):
    def __init__(self):
        pgrest_backend = CONFIG.get('postgrest_backend_address', 'global')
        self.method = None
        self.postgrest_url = f'http://{pgrest_backend}'
        self.translation_server = None
        self.definition_language = None
        self.language = None

        self._words_to_link = set()
        self._wordlist = set()
        self._current_file_size = 0
        self._batch_file_counter = 1
        self._current_file = None

    @property
    def additional_data_type(self):
        raise NotImplementedError()

    def get_words(self, page_number=1, words_per_page=10000):
        url = f'{self.postgrest_url}/unaggregated_dictionary'
        pages = requests.get(url, params={
            'limit': words_per_page,
            'offset': words_per_page * page_number,
            # 'definition_language': f'eq.{self.definition_language}',
            'language': f'eq.{self.language}',
            'order': 'definition_id.asc'
        })
        print(pages)
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        pages_as_json = pages.json()
        for page in pages_as_json:
            yield page

    def get_translation(self, text):
        raise NotImplementedError()

    def add_mt_translated_definition(self, definition_id, translated_definition, method):
        url = f'{self.postgrest_url}/mt_translated_definition'
        json = {
            'id': definition_id,
            'definition': translated_definition,
            'definition_language': 'mg',
            'method': method
        }
        print(url, json)
        request = requests.post(url, json=json)
        if 400 <= request.status_code <= 599:
            raise DefinitionTranslationError('Unknown error: ' + request.text)

    def process_definition(self, definition):
        return ENWiktionaryProcessor.refine_definition(definition)[0]

    def import_translations_from_json_dictionary_table(self, page_number=1):
        for word in self.get_json_dictionary(page_number, part_of_speech='ana', language='en,es,fr'):
            definitions = [d for d in word['definitions'] if d['language'] == self.definition_language]
            for definition in definitions:
                processed_definition = self.process_definition(definition['definition'])
                unwanted_character = False
                for character in "{}[]|":
                    if character in processed_definition:
                        unwanted_character = True
                        print("unwanted characters : '" + character + "'")
                        break
                if unwanted_character:
                    continue

                try:
                    translation = self.get_translation(processed_definition)

                    # The 1.6B model of NLLB sometimes gets stuck in a loop, which can be easily caught here
                    # which leads the translated definition to be more than double the size of the original definition
                    if len(translation) > 4 * len(definition['definition']):
                        continue

                    self.add_mt_translated_definition(
                        definition_id=definition['id'],
                        translated_definition=translation,
                        method=self.method
                    )
                    print(word['id'], self.additional_data_type, translation)
                except SyntaxError as error:
                    print("Error on import:", error)
                    continue

    def import_translations_from_definitions_table(self, page_number=1):
        for definition in self.get_definitions(page_number):
            print(definition)
            try:

                translation = self.get_translation(self.process_definition(definition['definition']))
                self.add_mt_translated_definition(
                    definition_id=definition['id'],
                    translated_definition=translation,
                    method=self.method
                )
                print(definition['id'], self.additional_data_type, translation)
            except Exception as error:
                print("Error on import:", error)
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

    def get_word_info_with_additional_data(self, items_per_page, start_from_page=1):
        total_pages = 100
        url = f'{self.postgrest_url}/word_with_' + self.additional_data_type
        for page_number in range(total_pages):
            print(f'(page {1 + page_number}/{total_pages}) getting {items_per_page} pages from database...')
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
        url = f'{self.postgrest_url}/unaggregated_dictionary'
        pages = requests.get(url, params={
            'word_id': f'eq.{word_id}',
        })
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        return pages.json()[0]

    def get_definitions_for_word(self, word_id):
        url = f'{self.postgrest_url}/unaggregated_dictionary'
        pages = requests.get(url, params={
            'word_id': f'eq.{word_id}',
            'definition_language': f'eq.{self.definition_language}',
        })
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        return [line['definition'] for line in pages.json()]

    def get_json_dictionary(self, page_number=1, results=10000, language=None, part_of_speech=None):
        url = f'{self.postgrest_url}/json_dictionary'
        request_parameters = {
            'limit': results,
            'offset': page_number,
            'order': 'id.asc'
        }
        if language is not None:
            if ',' in language:
                request_parameters['language'] = 'in.(' + language + ')'
            else:
                request_parameters['language'] = 'eq.' + language
        if part_of_speech is not None:
            request_parameters['part_of_speech'] = 'eq.' + part_of_speech

        pages = requests.get(url, params=request_parameters)
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        return pages.json()

    def get_definitions(self, page_number=1, results=10000):
        url = f'{self.postgrest_url}/definitions'
        pages = requests.get(url, params={
            'limit': results,
            'offset': page_number,
            'definition_language': f'eq.{self.definition_language}',
        })
        if pages.status_code != 200:
            print(pages.json())
            raise DefinitionTranslationError(pages.text)

        return pages.json()

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
            url = f'{self.postgrest_url}/word'
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
        url = f'{self.postgrest_url}/word'
        pages = requests.get(url, params={'id': f'eq.{word_id}'})
        if pages.status_code != 200:
            raise DefinitionTranslationError(pages.text)
        else:
            return pages.json()[0]['part_of_speech']

    def get_word_ids(self, words):
        words_as_csl = ','.join(words)
        url = f'{self.postgrest_url}/unaggregated_dictionary'
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
        pass

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

    def get_translated_definitions(self, word_id):
        return []

    def build_translation_batches(self, word_additional_data_info, counter=0):
        translation = Translation()
        batch_folder = 'user_data/translation_batch'
        # translation.output.wikipage_renderer.pages_to_link = self.malagasy_words_to_link
        word = word_additional_data_info['word']
        word_id = word_additional_data_info['word_id']
        definitions = self.get_definitions_for_word(word_id)
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
            try:
                word, word_id, en_definition, mg_definition = row[:4]
            except ValueError as error:
                print(error)
                continue
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


class OpenMtDefinitionTranslation(DefinitionTranslation):
    def __init__(self):
        super(OpenMtDefinitionTranslation, self).__init__()
        self.translation_server = CONFIG.get('backend_address', 'openmt')
        self.definition_language = 'fr'
        self.language = 'fr'
        self.method = 'openmt'

    @property
    def additional_data_type(self):
        return 'openmt_translation'

    def get_translation(self, text):
        url = f'http://{self.translation_server}/translate/{self.definition_language}/mg'
        json = {
            'text': text
        }
        request = requests.post(url, json=json)
        if request.status_code != 200:
            raise DefinitionTranslationError('Unknown error: ' + request.text)
        else:
            return request.json()['text']


class NllbDefinitionTranslation(DefinitionTranslation):
    def __init__(self):
        super(NllbDefinitionTranslation, self).__init__()
        self.translation_server = CONFIG.get('backend_address', 'nllb')
        self.method = 'nllb-1.6b'

        # Dictionary parameters
        self.definition_language = 'en'
        self.language = 'en'

        # Translator parameters
        self.translator_definition_language = 'en_Latn'
        self.translator_target_language = 'plt_Latn'

    @property
    def additional_data_type(self):
        return 'nllb_translation'

    def get_translation(self, text):
        url = f'http://{self.translation_server}/translate/' \
              f'{self.translator_definition_language}/' \
              f'{self.translator_target_language}'
        json = {
            'text': text
        }
        print(url, json)
        request = requests.get(url, params=json)
        if request.status_code != 200:
            raise DefinitionTranslationError('Unknown error: ' + request.text)
        else:
            return request.json()['translated']


if __name__ == '__main__':
    bot = NllbDefinitionTranslation()
    bot.import_translations_from_json_dictionary_table()
    # bot.publish_translated_definition()
