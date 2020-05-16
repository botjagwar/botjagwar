"""
use a mg.wiktionary.org dump and import all its contents to the botjagwar database.
"""
import time
from copy import deepcopy

from lxml import etree

# import pywikibot
from api.entryprocessor import WiktionaryProcessorFactory
from api.servicemanager import DictionaryServiceManager
from database.exceptions.http import BatchContainsErrors
from dump_processor import Processor
from object_model.word import Entry


class MgWiktionaryDumpImporter():
    _current_batch = []
    _n_items = 0
    batch_size = 10
    content_language = 'mg'

    def __init__(self, file_name):
        self.file_name = file_name
        self.processor = Processor()
        self.EntryProcessor = WiktionaryProcessorFactory.create('mg')
        self.entryprocessor = self.EntryProcessor()
        self.dictionary_service = DictionaryServiceManager()

    def batch_post(self):
        from pprint import pprint
        pprint(self._current_batch)
        response = self.dictionary_service.post('entry/batch', json=self._current_batch)
        err_msg = response.json()
        self._current_batch = []
        self._n_items = 0
        pprint(self._current_batch)
        #print(err_msg)
        if response.status_code in (400, 500, BatchContainsErrors.status_code):
            raise Exception('Error on batch send')

    def batch_push(self, info: Entry):
        """updates database"""
        # Adapt to expected format

        definitions = [{
            'definition': d,
            'definition_language': self.content_language
        } for d in info.entry_definition]
        data = {
            'definitions': definitions,
            'language': info.language,
            'word': info.entry,
            'part_of_speech': info.part_of_speech,
        }
        if self._n_items >= self.batch_size:
            self.batch_post()
        else:
            self._current_batch.append(data)
            self._n_items += 1

    def load(self):
        for _100_page_batch in self.processor.load(self.file_name):
            for xml_page in _100_page_batch:
                yield xml_page

    def process(self, xml_page):
        #print("processing page xml")
        node = etree.XML(str(xml_page))
        title_node = node.xpath('//title')[0].text
        content_node = node.xpath('//revision/text')[0].text
        self.entryprocessor.set_title(title_node)
        self.entryprocessor.set_text(content_node)
        dt = time.time()
        c = 0
        for entry in self.entryprocessor.getall():
            for definitions in entry.entry_definition:
                for definition in definitions.split(','):
                    new_entry = deepcopy(entry)
                    for char in '[]=':
                        definition = definition.replace(char, '')

                    new_entry.entry_definition = [definition.strip()]
                    self.batch_push(info=new_entry)
                    c += 1

            if not c >= 1000:
                q = 60. * c / (time.time() - dt)
                print('{} wpm'.format(q,))
                c = 0
                dt = time.time()

        self.batch_post()

    def run(self):
        for xml_page in self.load():
            self.process(xml_page)


if __name__ == '__main__':
    bot = MgWiktionaryDumpImporter('/home/rado/Downloads/mgwiktionary-20200501-pages-articles.xml')
    bot.run()
