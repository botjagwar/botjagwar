import time
from random import randint

import requests

from api.decorator import threaded
from api.entryprocessor.wiki.en import ENWiktionaryProcessor
from redis_wikicache import RedisSite

processor = ENWiktionaryProcessor()


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


def create_definition_if_not_exists(definition, language):
    def fetch_definition(definition, language):
        # Fetch definition
        dict_get_data = {
            'definition': f'eq.{definition}',
            'definition_language': f'eq.{language}'
        }

        resp = requests.get(PgrestServer().server + '/definitions', params=dict_get_data)
        returned_data = resp.json()
        return returned_data

    returned_data = fetch_definition(definition, language)
    # Add definition if not found
    if not returned_data:
        defn_post_data = {
            'definition': definition,
            'definition_language': language
        }
        resp = requests.post(PgrestServer().server + '/definitions', json=defn_post_data)
        return fetch_definition(definition, language)
    else:
        return returned_data


def reimport_english_definitions(page_nb=1):
    # definition_translation = NllbDefinitionTranslation()
    site = RedisSite('en', 'wiktionary')
    ct_time = time.time()
    counter = 0
    for page in site.all_pages():
        content = page.get()
        title = page.title()
        processor.title = title
        processor.content = content
        entries = [entry for entry in processor.get_all_entries()]
        for entry in entries:
            word = fetch_word(entry.entry, entry.language, entry.part_of_speech)
            if not word:
                # print(f"{entry.entry} ({entry.part_of_speech}, {entry.language})"
                #       f" No yet referenced in dictionary! Import skipped...")
                continue

            for definition in entry.definitions:
                counter += 1
                if not counter % 500:
                    dtime = abs(ct_time - time.time())
                    ct_time = time.time()
                    print(f'{counter} imported (throughput: {500 / dtime} entries/second)')
                _reimport_english_definition(word, definition)


@threaded
def _reimport_english_definition(word, definition):
    definition_data = create_definition_if_not_exists(definition, 'en')
    if definition_data:
        definition_data = definition_data[0]
    else:
        return

    dict_post_data = {
        'definition': f'{definition_data["id"]}',
        'word': f'{word["id"]}',
    }

    resp = requests.post(PgrestServer().server + '/dictionary', json=dict_post_data)


if __name__ == '__main__':
    reimport_english_definitions(p)
