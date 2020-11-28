import random
import time

import pywikibot
import requests

from api.importer import dyn_backend
from api.output import WikiPageRendererFactory, Output
from object_model.word import Entry


class SkippedWord(Exception):
    pass


class NinjaEntryPublisher(object):
    typo_reliability = 0.9983
    speed_wpm = 35
    random_latency = [10, 180]
    edit_session_length_minutes = [20, 220]
    overwrite = False

    def __init__(self):
        self.session_start = time.time()
        self.session_length = random.randint(
            self.edit_session_length_minutes[0],
            self.edit_session_length_minutes[1]
        )

    def publish(self, entry, title, wikitext, summary_if_exists, summary_if_new):
        print(wikitext)
        ct_time = time.time()
        if (ct_time - self.session_start)/60 > self.session_length * 60:
            print('Session over! Waiting 17 hours before publishing again')
            time.sleep(17*3600)

        wikipage = pywikibot.Page(pywikibot.Site('mg', 'wiktionary'), title)
        min_sleeptime = (len(wikitext) / 6) // self.speed_wpm
        sleep = min_sleeptime + random.randint(self.random_latency[0], self.random_latency[1])
        if wikipage.exists():
            contents = wikipage.get()
            if '{{=' + entry.language + '=}}' in contents:
                if self.overwrite:
                    print('overwriting')
                    summary = '+tsiahy, sns.'
                    print('waited %d seconds' % sleep)
                    wikipage.put(wikitext, summary, minor=False)
                    time.sleep(sleep/5)

                else:
                    print('skipped page as already exists')
            else:
                summary = summary_if_exists + ' Fizarana vaovao'
                print('waited %d seconds' % sleep)
                contents = wikitext + '\n\n' + contents
                wikipage.put(contents, summary, minor=False)
                time.sleep(sleep)
        else:
            print('waited %d seconds' % sleep)
            summary = summary_if_new
            wikipage.put(wikitext, summary, minor=False)
            time.sleep(sleep)


class NinjaEntryCreator(object):

    def __init__(self):
        Renderer = WikiPageRendererFactory('mg')
        self.publisher = NinjaEntryPublisher()
        self.output = Output()
        self.renderer = Renderer()
        mg_word_list = self.fetch_mg_word_list()
        self.renderer.pages_to_link = mg_word_list
        additional_data_types_rq = requests.get(dyn_backend.backend + '/additional_word_information_types')
        self.additional_data_types = set()
        if additional_data_types_rq == 200:
            self.additional_data_types = {
                d['type'] for d in additional_data_types_rq.json()
            }

    def fetch_mg_word_list(self):
        params = {
            'language': 'eq.mg',
            'part_of_speech': 'in.(ana,mat,mpam)'
        }

        resp = requests.get(dyn_backend.backend + '/word', params=params)
        assert resp.status_code == 200
        ret = [w['word'] for w in resp.json()]
        return set(ret)

    def fetch_additional_data(self, additional_data_list, word_id, type_, return_as=(str, list)) -> [str, list]:
        if return_as == str:
            for data in additional_data_list[0]:
                if data['type'] == type_:
                    return data['data']
        else:
            ret = []
            for dic in additional_data_list:
                if dic['data_type'] == type_:
                    ret.append(dic['data'])
            return ret

    def run(self, language=None):
        params = {
            #'limit': 1000,
            # 'offset': 1100,
            # 'en_definition': 'eq.' + sys.argv[1],
            # 'language': 'neq.mg',
            'order': 'word_id',
            #'suggested_definition': 'eq.' + sys.argv[1],
            # 'word_id': 'eq.471733'
            # 'part_of_speech': 'eq.mat'
        }
        if language is not None:
            params['language'] = 'eq.' + language

        convergent_translations_rq = requests.get(dyn_backend.backend + '/convergent_translations', params=params)
        if convergent_translations_rq.status_code != 200:
            print('convergent_translations_rq.status_code', convergent_translations_rq.status_code)
            return

        for translation in convergent_translations_rq.json():
            title = translation['word']
            print('>>>>>  ' + title + '  <<<<<')
            try:
                entry, wikistring, summary_if_new, summary_if_exists = self.generate_wikipage_and_summaries(translation)
                summary_if_new = "Pejy voaforona amin'ny « " + summary_if_new + ' »'
                self.publisher.publish(entry, title, wikistring, summary_if_exists, summary_if_new)
            except SkippedWord:
                print('skipped')
            else:
                self.output.db(entry)

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
                'ipa': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'IPA', list),
                'audio_pronunciations': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'audio', list),
                # 'related_terms': self.fetch_additional_data(
                #     additional_data_list, translation['word_id'], 'related', list),
                # 'derived_terms': self.fetch_additional_data(
                #     additional_data_list, translation['word_id'], 'derived', list),
                # 'references': ['{{Tsiahy:vortaro.net}}'],
                # 'references': self.fetch_additional_data(
                #     additional_data_list, translation['word_id'], 'reference', list),
                # 'etymology': self.fetch_additional_data(
                #     additional_data_list, translation['word_id'], 'etym/en', str)
            }
            additional_data_dict = {
                k: v for k, v in raw_additional_data_dict.items() if v
            }
            print(raw_additional_data_dict )
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
            summary_if_already_exists = '/* {{=' + translation["language"] + '=}} */'

            return entry, wiki_string, summary_if_new, summary_if_already_exists
        else:
            print('definitions', definitions)
            raise SkippedWord()


if __name__ == '__main__':
    entry_creator = NinjaEntryCreator()
    # if len(sys.argv) > 1:
    #     entry_creator.run(sys.argv[1])
    # else:
    entry_creator.run()
