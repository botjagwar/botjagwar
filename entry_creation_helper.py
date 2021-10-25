import csv
import random
import time

import pywikibot
import requests

from api.decorator import singleton
from api.model.word import Entry
# from api.importer.wiktionary import dyn_backend
from api.output import WikiPageRendererFactory, Output
from api.servicemanager.pgrest import StaticBackend

dyn_backend = StaticBackend()


class SkippedWord(Exception):
    pass


@singleton
class RandomLatency(object):
    random_latency = [10, 25]
    min_sleeptime = 10

    @property
    def latency(self) -> int:
        return self.min_sleeptime + \
            random.randint(self.random_latency[0], self.random_latency[1])


class NinjaEntryPublisher(object):
    typo_reliability = 0.9983
    speed_wpm = 35
    overwrite = False

    def publish(
            self,
            entry,
            title,
            wikitext,
            summary_if_exists,
            summary_if_new):
        wikipage = pywikibot.Page(pywikibot.Site('mg', 'wiktionary'), title)
        sleep = RandomLatency().latency
        if wikipage.exists():
            contents = wikipage.get()
            if '{{=' + entry.language + '=}}' in contents:
                if self.overwrite:
                    print('overwriting')
                    summary = '+tsiahy, sns.'
                    print('waited %d seconds' % sleep)
                    wikipage.put(wikitext, summary, minor=False)
                    time.sleep(sleep / 5)
                else:
                    return
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
        additional_data_types_rq = requests.get(
            dyn_backend.backend + '/additional_word_information_types')
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

    def fetch_additional_data(self, additional_data_list,
                              word_id, type_, return_as=(str, list)) -> [str, list]:
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

    def run_from_csv(self, csv_path, language='la'):
        with open(csv_path, 'r') as csv_file:
            reader = csv.reader(csv_file, delimiter=';')
            for row in reader:
                title, pos, en_defn, mg_defn = row[:4]
                if not mg_defn.strip():
                    continue

                pos = pos.strip()
                mg_defn = mg_defn[0].upper() + mg_defn[1:].lower()

                print('>>>>> ' + title + ' <<<<<')

                try:
                    entry_data = {
                        'entry': title,
                        'language': language,
                        'part_of_speech': pos,
                        'definitions': [mg_defn],
                    }

                    entry = Entry(**{**entry_data})
                    wiki_string = self.renderer.render(entry)
                    summary_if_new = wiki_string.replace('\n', ' ')
                    summary_if_already_exists = '/* {{=' + language + '=}} */'

                    summary_if_new = "Pejy voaforona amin'ny « " + summary_if_new + ' »'
                    print(entry)
                    self.publisher.publish(
                        entry,
                        title,
                        wiki_string,
                        summary_if_already_exists,
                        summary_if_new)
                except SkippedWord:
                    continue
                else:
                    self.output.db(entry)

    def run_from_database(self, language=None):
        params = {
            'limit': 30000,
            # 'offset': 1100,
            # 'en_definition': 'eq.' + sys.argv[1],
            'language': 'not.in.(mg,fr,en)',
            # 'order': 'word_id',
            # 'suggested_definition': 'eq.' + sys.argv[1],
            # 'word_id': 'gt.469562'
            # 'part_of_speech': 'eq.mat'
        }
        # if language is not None:
        #     params['language'] = 'eq.' + language

        convergent_translations_rq = requests.get(
            dyn_backend.backend + '/convergent_translations', params=params)
        if convergent_translations_rq.status_code != 200:
            print('convergent_translations_rq.status_code',
                  convergent_translations_rq.status_code)
            return

        new_associations_rq = requests.get(
            dyn_backend.backend + '/new_associations', params={})
        if new_associations_rq.status_code != 200:
            print(
                'new_associations_rq.status_code',
                new_associations_rq.status_code)
            return

        new_associations = [(d['word'], d['definition'])
                            for d in new_associations_rq.json()]
        data = convergent_translations_rq.json()
        print(len(new_associations), 'associations loaded')
        print(new_associations[:10])
        print(data[:10])
        print(len(data), 'translations loaded')
        filtered_data = []
        for translation in data:
            if (int(translation['word_id']), int(
                    translation['mg_definition_id'])) in new_associations:
                continue
            else:
                filtered_data.append(translation)

        print(len(filtered_data), 'filtered translations loaded')
        for translation in filtered_data:
            title = translation['word']
            print(translation['word_id'], translation['mg_definition_id'])

            print('>>>>> ' + title + ' <<<<<')
            try:
                entry, wikistring, summary_if_new, summary_if_exists = self.generate_wikipage_and_summaries(
                    translation)
                summary_if_new = "Pejy voaforona amin'ny « " + summary_if_new + ' »'
                self.publisher.publish(
                    entry,
                    title,
                    wikistring,
                    summary_if_exists,
                    summary_if_new)
            except SkippedWord:
                continue
            else:
                self.output.db(entry)

    def generate_wikipage_and_summaries(self, translation):
        # Fetching base information
        json_dictionary_infos_params = {
            'id': 'eq.' + str(translation["word_id"])
        }
        json_dictionary_rq = requests.get(
            dyn_backend.backend + '/vw_json_dictionary',
            params=json_dictionary_infos_params)

        if json_dictionary_rq.status_code == 200:
            json_dictionary_infos = json_dictionary_rq.json()
            additional_data = json_dictionary_infos[0]['additional_data']
        else:
            print(
                'json_dictionary_rq.status_code',
                json_dictionary_rq.status_code)
            raise SkippedWord()

        definitions = []
        request_convergent_definition_rq = requests.get(
            dyn_backend.backend + '/convergent_translations', params={
                'word_id': 'eq.' + str(translation["word_id"])
            }
        )
        if request_convergent_definition_rq.status_code == 200:
            definitions = [e['suggested_definition']
                           for e in request_convergent_definition_rq.json()]
        else:
            print('request_convergent_definition_rq.status_code ',
                  request_convergent_definition_rq.status_code)

        # Fetching and mapping additional data
        additional_data_list = json_dictionary_infos[0]['additional_data']
        if additional_data_list is not None:
            # p = self.fetch_additional_data(
            # additional_data_list, translation['word_id'], 'pronunciation',
            # list)
            raw_additional_data_dict = {
                'synonyms': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'synonym', list),
                'antonyms': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'antonym', list),
                'ipa': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'ipa', list),
                # 'pronunciation': p[0] if p else [],
                # 'ipa': ['{{fanononana-ko}}'],
                'audio_pronunciations': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'audio', list),
                'related_terms': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'related', list),
                'derived_terms': self.fetch_additional_data(
                    additional_data_list, translation['word_id'], 'derived', list),
                # 'references': ['{{Tsiahy:vortaro.net}}'],
                # 'references': self.fetch_additional_data(
                #     additional_data_list, translation['word_id'], 'reference', list),
                # 'etymology': self.fetch_additional_data(
                #     additional_data_list, translation['word_id'], 'etym/en', str)
            }
            additional_data_dict = {
                k: v for k, v in raw_additional_data_dict.items() if v
            }
            print(raw_additional_data_dict)
        else:
            additional_data_dict = {}

        # Compiling final object
        if definitions:
            entry_data = {
                'entry': translation["word"],
                'language': translation["language"],
                'part_of_speech': translation["part_of_speech"],
                'definitions': definitions,
            }

            for data_type in self.additional_data_types:
                if data_type in additional_data:
                    entry_data[data_type] = additional_data[data_type]

            entry = Entry(**{**entry_data, **additional_data_dict})
            wiki_string = self.renderer.render(entry)
            summary_if_new = wiki_string.replace('\n', ' ')
            summary_if_already_exists = '/* {{=' + \
                translation["language"] + '=}} */'
            if len(summary_if_new) > 147:
                summary_if_new = summary_if_new[:147] + '...'
            return entry, wiki_string, summary_if_new, summary_if_already_exists
        else:
            print('definitions', definitions)
            raise SkippedWord()


if __name__ == '__main__':
    entry_creator = NinjaEntryCreator()
    import sys
    entry_creator.run_from_database(sys.argv[1])
    # if len(sys.argv) > 1:
    #     entry_creator.run(sys.argv[1])
    # else:
    #entry_creator.run_from_csv("user_data/cache_extractor/la_Latin nouns.csv")
