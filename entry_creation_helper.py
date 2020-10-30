import random
import sys
import time

import pywikibot
import requests

from additional_data_importer import dyn_backend
from api.output import WikiPageRendererFactory
from object_model.word import Entry


class SkippedWord(Exception):
    pass


class NinjaEntryPublisher(object):
    typo_reliability = 0.9983
    speed_wpm = 35
    random_latency = [40, 130]
    edit_session_length_minutes = [1, 1]

    def __init__(self):
        self.timer = time.time()
        self.session_length = random.randint(
            self.edit_session_length_minutes[0],
            self.edit_session_length_minutes[1]
        )

    def publish(self, entry, title, wikitext, summary_if_exists, summary_if_new):
        ct_time = time.time()
        if (ct_time - self.timer)/60 > self.session_length * 60:
            print('Session over! Waiting 17 hours before publishing again')
            time.sleep(17*3600)

        wikipage = pywikibot.Page(pywikibot.Site('mg', 'wiktionary'), title)
        min_sleeptime = (len(wikitext) / 6) // self.speed_wpm
        sleep = min_sleeptime + random.randint(self.random_latency[0], self.random_latency[1])
        if wikipage.exists():
            contents = wikipage.get()
            if '{{=' + entry.language + '=}}' in contents:
                print('skipped page as already exists')
            else:
                print('waited %d seconds' % sleep)
                summary = summary_if_exists + ' : Fizarana vaovao'
                print(summary)
                contents = wikitext + '\n\n' + contents
                time.sleep(sleep)
                wikipage.put(contents, summary)
        else:
            print('waited %d seconds' % sleep)
            summary = summary_if_new
            print(summary)
            time.sleep(sleep)
            wikipage.put(wikitext, summary)


class NinjaEntryCreator(object):

    def __init__(self):
        Renderer = WikiPageRendererFactory('mg')
        self.publisher = NinjaEntryPublisher()
        self.renderer = Renderer()
        additional_data_types_rq = requests.get(dyn_backend.backend + '/additional_word_information_types')
        self.additional_data_types = set()
        if additional_data_types_rq == 200:
            self.additional_data_types = {
                d['type'] for d in additional_data_types_rq.json()
            }

    def fetch_additional_data(self, additional_data_list, word_id, type_, return_as=(str, list)) -> [str, list]:
        if return_as == str:
            for data in additional_data_list:
                if data['type'] == type_:
                    return data['information']
        else:
            return [
                d['information']
                for d in additional_data_list
                if d['type'] == type_
            ]

    def run(self, language=None):
        params = {
            'limit': 40,
            'offset': 0,
            'part_of_speech': 'eq.mat'
        }
        if language is not None:
            params['language'] = 'eq.' + language

        convergent_translations_rq = requests.get(dyn_backend.backend + '/convergent_translations', params=params)
        if convergent_translations_rq.status_code != 200:
            print('convergent_translations_rq.status_code', convergent_translations_rq.status_code)
            return

        for translation in convergent_translations_rq.json():
            try:
                title = translation['word']
                entry, wikistring, summary_if_new, summary_if_exists = self.generate_wikipage_and_summaries(translation)
                print('>>>>>  ' + title + '  <<<<<')
                print(wikistring + '\n')
                summary_if_new = "Pejy voaforona amin'ny « " + summary_if_new + ' »'
                print(summary_if_exists)
                print(len(wikistring))
                self.publisher.publish(entry, title, wikistring, summary_if_exists, summary_if_new)
            except SkippedWord:
                continue

    def generate_wikipage_and_summaries(self, translation):
        # Fetching base information
        json_dictionary_infos_params = {
            'id': 'eq.' + str(translation["word_id"])
        }
        json_dictionary_rq = requests.get(dyn_backend.backend + '/vw_json_dictionary',
                                          params=json_dictionary_infos_params)

        if json_dictionary_rq.status_code == 200:
            json_dictionary_infos = json_dictionary_rq.json()
            additional_data = json_dictionary_infos[0]['additional_data']
        else:
            print('json_dictionary_rq.status_code', json_dictionary_rq.status_code)
            raise SkippedWord()

        definitions = []
        request_convergent_definition_rq = requests.get(
            dyn_backend.backend + '/convergent_translations', params={
                'word_id': 'eq.' + str(translation["word_id"])
            }
        )
        if request_convergent_definition_rq.status_code == 200:
            definitions = [
                e['suggested_definition'] for e in request_convergent_definition_rq.json()
            ]
        else:
            print('request_convergent_definition_rq.status_code ', request_convergent_definition_rq.status_code)


        # Fetching and mapping additional data
        additional_data_list = json_dictionary_infos[0]['additional_data']
        if additional_data_list is not None:
            raw_additional_data_dict = {
                'synonyms': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'synonym', list),
                'antonyms': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'antonym', list),
                'audio_pronunciations': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'IPA', list),
                'etymology': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'etym/en', str)
            }
            additional_data_dict = {
                k: v for k, v in raw_additional_data_dict.items() if v
            }
        else:
            additional_data_dict = {}

        # Compiling final object
        if definitions:
            entry_data = {
                'entry': translation["word"],
                'language': translation["language"],
                'part_of_speech': translation["part_of_speech"],
                'entry_definition': definitions,
            }

            for data_type in self.additional_data_types:
                if data_type  in additional_data:
                    entry_data[data_type ] = additional_data[data_type]

            entry = Entry(**{**entry_data, **additional_data_dict})
            wiki_string = self.renderer.render(entry)
            summary_if_new = wiki_string.replace('\n', ' ')
            summary_if_already_exists = '/* =={{=' + translation["language"] + '=}}== */'

            return entry, wiki_string, summary_if_new, summary_if_already_exists
        else:
            print('definitions', definitions)


if __name__ == '__main__':
    entry_creator = NinjaEntryCreator()
    if len(sys.argv) > 1:
        entry_creator.run(sys.argv[1])
    else:
        entry_creator.run()
