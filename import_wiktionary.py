"""
use a mg.wiktionary.org dump and import all its contents to the botjagwar database.
"""
import argparse
import time
from copy import deepcopy

import psycopg2.errors
import redis
from lxml import etree

from api.config import BotjagwarConfig
from api.decorator import time_this
from api.dictionary.exceptions.http import BatchContainsErrors
from api.entryprocessor import WiktionaryProcessorFactory
from api.model.word import Entry
from api.servicemanager import DictionaryServiceManager
from dump_processor import Processor

config = BotjagwarConfig()


class WiktionaryDumpImporter(object):
    content_language = ''
    _current_batch = []
    _insert = {}
    _n_items = 0
    batch_size = 5000

    def __init__(self, file_name):
        self.file_name = file_name
        self.processor = Processor('en')
        self._init_processor()
        self.dictionary = redis.Redis(config.get('host', 'redis'))
        # self._init_redis_cache()
        # self.additional_data_keys = set(classe.data_type for classe in all_importers)
        # print(self.additional_data_keys)

    def _init_redis_cache(self):
        """
        Import ID mappings to existing redis instance to reduce start time.
        start/restart time takes several minutes in proportion with the number of words.
        Redis is used to reduce network-induced latency.
        :return:
        """
        key = 'WiktionaryDumpImporter/is_cache_initialised'
        if self.dictionary.get(key) == '1':
            print('Skipping redis cache initialization')
            return

        pgsql_conn = psycopg2.connect(config.get('database_uri'))
        cursor = pgsql_conn.cursor()

        sql = cursor.mogrify(
            "select id, word, part_of_speech, language from word")
        cursor.execute(sql)
        count = 0
        for id_, word, pos, lang in cursor:
            count += 1
            if not count % 1000:
                print(count)
            key = '/'.join((word, pos, lang))
            self.dictionary.set(key, id_)

        self.dictionary.set(key, '1')

    def _init_processor(self):
        self.EntryProcessor = WiktionaryProcessorFactory.create(
            self.content_language)
        self.entryprocessor = self.EntryProcessor()
        self.dictionary_service = DictionaryServiceManager()

    def batch_post(self):
        response = self.dictionary_service.post(
            'entry/batch', json=self._current_batch)
        self._current_batch = []
        self._n_items = 0
        if response.status_code in (400, 500, BatchContainsErrors.status_code):
            raise Exception('Error on batch send')

    def batch_push(self, info: Entry):
        """updates database"""
        # Adapt to expected format

        definitions = [{
            'definition': d,
            'definition_language': self.content_language
        } for d in info.definitions]
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

    def get_page_from_xml(self, xml_page):
        node = etree.XML(str(xml_page))
        title_node = node.xpath('//title')[0].text
        content_node = node.xpath('//revision/text')[0].text
        return title_node, content_node

    def import_wiktionary_page(self, xml_page):
        title_node, content_node = self.get_page_from_xml(xml_page)
        self.entryprocessor.set_title(title_node)
        self.entryprocessor.set_text(content_node)
        for entry in self.entryprocessor.get_all_entries():
            for definitions in entry.definitions:
                for definition in definitions.split(','):
                    new_entry = deepcopy(entry)
                    for char in '[]=':
                        definition = definition.replace(char, '')

                    new_entry.definitions = [definition.strip()]
                    self.batch_push(info=new_entry)

        self.batch_post()

    @staticmethod
    @time_this()
    def do_insert(_insert: dict, level=0):
        pgsql_conn = psycopg2.connect(config.get('database_uri'))
        cursor = pgsql_conn.cursor()
        n_elements = 0
        sql = b"insert into additional_word_information (word_id, type, information) values "
        for wid, type_, _data in _insert:
            n_elements += 1
            sql += cursor.mogrify("(%s, %s, %s),", (wid, type_, _data))

        try:
            cursor.execute(sql[:-1])
        except psycopg2.Error as error:
            from pprint import pprint
            if psycopg2.errors.lookup(error.pgcode) == '23505':
                pprint(' ' * level + 'Duplicate entry error. Splitting batch')
                elements = len(_insert.items())
                if elements > 2:
                    WiktionaryDumpImporter.do_insert(
                        elements[:elements // 2], level + 1)
                    WiktionaryDumpImporter.do_insert(
                        elements[1 + elements // 2:], level + 1)
                else:
                    pprint('[reset indent] could not insert:', elements)

        except Exception as unknown_error:
            print(sql)
            raise unknown_error
        else:
            pgsql_conn.commit()

        if n_elements > 0:
            pgsql_conn.close()

    def import_additional_data(self, xml_page):
        batch_size = self.batch_size
        title_node, content_node = self.get_page_from_xml(xml_page)
        self.entryprocessor.set_title(title_node)
        self.entryprocessor.set_text(content_node)

        for entry in self.entryprocessor.get_all_entries(get_additional_data=True):
            # print(entry)
            additional_data = {}
            for adt in self.additional_data_keys:
                if hasattr(entry, adt):
                    additional_data[adt] = getattr(entry, adt)

            for additional_data_type, data in additional_data.items():
                key = '/'.join((entry.entry,
                                entry.part_of_speech,
                                entry.language))
                if not self.dictionary.get(key):
                    continue

                word_id = self.dictionary.get(key)
                if isinstance(data, list):
                    data = set(data)
                    for datum in data:
                        self._n_items += 1
                        key = (int(word_id), additional_data_type, datum)
                        self._insert[key] = 0
                elif isinstance(data, str):
                    self._n_items += 1
                    key = (int(word_id), additional_data_type, data)
                    self._insert[key] = 0

                if self._n_items > batch_size:
                    print(
                        f'import_additional_data: uploading {batch_size} items...')
                    self.do_insert(self._insert)
                    self._n_items = 0
                    self._insert = {}

    def run(self):
        c = 0
        dt = time.time()
        for xml_page in self.load():
            c += 1
            try:
                # self.import_additional_data(xml_page)
                self.import_wiktionary_page(xml_page)
            except Exception as exc:
                print(exc)
                continue
            if c >= 1000:
                q = 60. * c / (time.time() - dt)
                print('{} wpm'.format(q))
                c = 0
                dt = time.time()

        self.do_insert(self._insert)


class MgWiktionaryDumpImporter(WiktionaryDumpImporter):
    content_language = 'mg'
    batch_size = 2500


class EnWiktionaryDumpImporter(WiktionaryDumpImporter):
    content_language = 'en'
    batch_size = 2500


class FrWiktionaryDumpImporter(WiktionaryDumpImporter):
    content_language = 'fr'
    batch_size = 2500


def main():
    parser = argparse.ArgumentParser(description='Import Wiktionary XML dump')
    parser.add_argument(
        '--dump',
        dest='dump',
        action='store',
        help='tube name')
    parser.add_argument(
        '--wiki',
        dest='wiki',
        action='store',
        help='instance name')

    args = parser.parse_args()
    assert args.wiki is not None
    assert args.dump is not None
    source_wiki = args.wiki.title().strip()
    dumpfile = args.dump.strip()
    DumpImporter = eval(f'{source_wiki}WiktionaryDumpImporter')
    bot = DumpImporter(dumpfile)
    print(bot)
    bot.run()


if __name__ == '__main__':
    main()
