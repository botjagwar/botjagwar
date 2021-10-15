from threading import Lock

import requests

from api.decorator import critical_section
from api.importer import AdditionalDataImporter
from api.importer import AdditionalDataImporterError
from api.importer.wiktionary import dyn_backend

rmi_lock = Lock()


class DictionaryImporter(AdditionalDataImporter):
    def populate_cache(self, language):
        rq_params = {
            'language': 'eq.' + language
        }
        response = requests.get(dyn_backend.backend + '/word', rq_params)
        query = response.json()
        for json in query:
            self.word_id_cache[(json['word'], json['language'])] = json['id']


class TenyMalagasyImporter(DictionaryImporter):
    data_type = 'tenymalagasy/definition'


class RakibolanaMalagasyImporter(DictionaryImporter):
    data_type = 'rakibolana/definition'

    @critical_section(rmi_lock)
    def write_tif(self, title, language, additional_data):
        temp = self.data_type
        self.data_type = 'rakibolana/derived'
        try:
            self.write_additional_data(title, language, additional_data)
        except AdditionalDataImporterError as exc:
            pass
        self.data_type = temp

    @critical_section(rmi_lock)
    def write_raw(self, title, language, additional_data):
        temp = self.data_type
        self.data_type = 'rakibolana/raw'
        try:
            self.write_additional_data(title, language, additional_data)
        except AdditionalDataImporterError as exc:
            pass
        self.data_type = temp

    def get_data(self, template_title: str, wikipage: str, language: str):
        pass
