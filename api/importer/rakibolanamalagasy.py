from threading import Lock

import requests

from api.importer import AdditionalDataImporter
from api.importer import AdditionalDataImporterError
from api.servicemanager.pgrest import StaticBackend

rmi_lock = Lock()
backend = StaticBackend()


class DictionaryImporter(AdditionalDataImporter):
    def populate_cache(self, language):
        rq_params = {
            'language': 'eq.' + language
        }
        response = requests.get(backend.backend + '/word', rq_params)
        query = response.json()
        for json in query:
            self.word_id_cache[(json['word'], json['language'], json['part_of_speech'])] = json['id']

    def get_word_id(self, word, language, part_of_speech):
        if (word, language, part_of_speech) not in self.word_id_cache:
            return self.http_get_word_id(word, language, part_of_speech)
        else:
            return self.word_id_cache[(word, language, part_of_speech)]

    def http_get_word_id(self, word, language, part_of_speech):
        rq_params = {
            'word': 'eq.' + word,
            'language': 'eq.' + language,
            'part_of_speech': 'eq.' + part_of_speech,
        }
        response = requests.get(backend.backend + '/word', rq_params)
        query = response.json()
        for json in query:
            self.word_id_cache[(json['word'], json['language'], json['part_of_speech'])] = json['id']

        if (word, language, part_of_speech) in self.word_id_cache:
            return self.word_id_cache[(word, language, part_of_speech)]


class TenyMalagasyImporter(DictionaryImporter):
    data_type = 'tenymalagasy/definition'


class RakibolanaMalagasyImporter(DictionaryImporter):
    data_type = 'rakibolana/definition'

    def write_tif(self, title, language, additional_data):
        temp = self.data_type
        self.data_type = 'rakibolana/derived'
        try:
            for pos in ['ana', 'mat', 'mpam']:
                word_id = self.get_word_id(title, language, pos)
                if word_id is not None:
                    break
            if word_id is None:
                raise AdditionalDataImporterError()
            self.write_additional_data(word_id, additional_data=additional_data)
        except AdditionalDataImporterError as exc:
            print(exc)

        self.data_type = temp

    def write_raw(self, title, language, additional_data):
        temp = self.data_type
        self.data_type = 'rakibolana/raw'
        try:
            for pos in ['ana', 'mat', 'mpam']:
                word_id = self.get_word_id(title, language, pos)
                if word_id is not None:
                    break
            if word_id is None:
                raise AdditionalDataImporterError()
            self.write_additional_data(word_id, additional_data=additional_data)
        except AdditionalDataImporterError as exc:
            pass
        self.data_type = temp

    def get_data(self, template_title: str, wikipage: str, language: str):
        pass
