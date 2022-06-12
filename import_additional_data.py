import argparse
import time
from threading import Thread

import requests

from api.decorator import retry_on_fail
from api.entryprocessor.wiki.en import ENWiktionaryProcessor
from api.extractors.site_extractor import RakibolanaSiteExtactor
from api.extractors.site_extractor import SiteExtractorException
from api.extractors.site_extractor import TenyMalagasySiteExtractor
from api.importer import AdditionalDataImporterError
from api.importer.rakibolanamalagasy import RakibolanaMalagasyImporter
from api.importer.rakibolanamalagasy import TenyMalagasyImporter
from api.page_lister import redis_get_pages_from_category as get_pages_from_category
from api.servicemanager.pgrest import DynamicBackend
from redis_wikicache import RedisSite

backend = DynamicBackend()


class TenyMalagasyPickleImporter(object):
    def __init__(self, args=None):
        self.importer = TenyMalagasyImporter(dry_run=False)
        self.extractor = TenyMalagasySiteExtractor()
        # self.importer.populate_cache('mg')

    def run(self):
        counter = 0
        to_reach = 0
        for page in get_pages_from_category('mg', "Anarana iombonana amin'ny teny malagasy"):
            counter += 1
            print(counter)
            if counter <= to_reach:
                continue

            try:
                entry = self.extractor.lookup(page.title())
            except SiteExtractorException:
                continue

            if not entry.definitions:
                continue
            else:
                print('>>> %s <<<' % entry.entry)
                self.process_rakibolana_definition(entry)

    def process_rakibolana_definition(self, entry):
        definitions = entry.definitions
        for definition in definitions:
            try:
                for pos in ['ana', 'mat', 'mpam']:
                    word_id = self.importer.get_word_id(entry.entry, entry.language, pos)
                    if word_id is not None:
                        break

                if word_id is None:
                    raise AdditionalDataImporterError()

                self.importer.write_additional_data(word_id, definition)

            except Exception as exception:
                print(exception)


class RakibolanaOrgPickleImporter(object):
    def __init__(self):
        self.importer = RakibolanaMalagasyImporter(dry_run=False)
        self.extractor = RakibolanaSiteExtactor()
        # self.importer.populate_cache('mg')

    def run(self):
        counter = 0
        to_reach = 0
        for pos in ['Matoanteny', 'Mpamaritra', 'Fomba fiteny']:
            for page in get_pages_from_category('mg', f"{pos} amin'ny teny malagasy"):
                counter += 1
                print(counter)
                if counter <= to_reach:
                    continue

                try:
                    entry = self.extractor.lookup(page.title())
                except SiteExtractorException:
                    continue

                if not entry.definitions:
                    continue
                else:
                    print('>>> %s <<<' % entry.entry)
                    self.process_rakibolana_definition(entry)

    def process_rakibolana_definition(self, entry):
        definitions = entry.definitions
        definition = definitions[0]
        definition = definition.replace('amim$$', 'amim-')
        raw_definition = definition.replace('$$', '|')

        if raw_definition.strip():
            self.importer.write_raw(entry.entry, 'mg', raw_definition)

        # definition listings
        pz = definition.find('$$')
        defn1 = definition[:pz]
        if '(' in defn1 and ')' in defn1:
            new_pz = definition.find('$$', pz)
            defn1 = definition[:new_pz].replace('$$', '')

        if not defn1:
            return

        try:
            for pos in ['ana', 'mat', 'mpam']:
                word_id = self.importer.get_word_id(entry.entry, entry.language, pos)
                if word_id is not None:
                    break

            if word_id is None:
                raise AdditionalDataImporterError()

            self.importer.write_additional_data(word_id, defn1)
        except AdditionalDataImporterError as exc:
            pass

        # t.i.f listings
        if definition.find('t$$i$$f$$$$') != -1:
            p1 = definition.rfind('t$$i$$f$$$$') + len('t$$i$$f$$$$')
            p2 = definition.find('$$', p1)
            tif = definition[p1:p2]
            if tif:
                for char in ',/1':
                    tif = tif.replace(char, '|')
                tif = tif.replace(' f ', '|')
                tif = tif.replace(' j ', '|')
                tif = tif.replace(' l ', '|')
                tifs = [w.strip().lower() for w in tif.split('|')]
                for tif in tifs:
                    self.importer.write_tif(entry.entry, 'mg', tif)


class EnWiktionaryAdditionalDataImporter(object):
    """
    This data importer requires Redis to import all the data from the English Wiktionary.
    """
    dump_path = 'user_data/dumps/enwikt.xml'
    url = 'https://dumps.wikimedia.org/enwiktionary/latest/enwiktionary-latest-pages-articles.xml.bz2'

    def __init__(self, args=None):
        if args is not None:
            if hasattr(args, 'start_page'):
                self.page_number_to_resume_to = int(args.start_page)
            else:
                self.page_number_to_resume_to = 0

        self.site = RedisSite('en', 'wiktionary')
        self.site.load_xml_dump(download_dump=True)

    def get_word_id(self, infos):
        data = {
            'word': 'eq.' + infos.entry,
            'language': 'eq.' + infos.language,
            'part_of_speech': 'eq.' + infos.part_of_speech,
            'limit': '1'

        }
        # log.debug('get /word', data)
        word_id = requests.get(backend.backend + '/word', params=data).json()
        if len(word_id) > 0:
            if 'id' in word_id[0]:
                word_id = word_id[0]['id']
                return word_id
            else:
                return
        else:
            return

    @retry_on_fail(exceptions=[requests.exceptions.ConnectionError], retries=5, time_between_retries=1)
    def upload_additional_data(self, word_id: int, additional_data_type: str, additional_data: str):
        if isinstance(additional_data, list):
            for data in additional_data:
                self.upload_additional_data(word_id, additional_data_type, data)
        else:
            data = {
                'type': additional_data_type,
                'word_id': word_id,
                'information': additional_data,
            }
            response = requests.post(
                backend.backend +
                '/additional_word_information',
                json=data)
            if 400 <= response.status_code <= 599:
                print(f'{data}')
                print(f'import {additional_data_type} to word_id {word_id} failed: HTTP {response.status_code}: {response.text}')
                return False
            elif response.status_code < 400:
                # print(f'import {additional_data_type} to word_id {word_id} OK: HTTP {response.status_code}')
                return True

    def delete_all_additional_data_of_type(self, word_id, additional_data_type):
        data = {
            'type': 'eq.' + additional_data_type,
            'word_id': 'eq.' + str(word_id),
        }
        response = requests.delete(
            backend.backend +
            '/additional_word_information',
            params=data)
        if 204 == response.status_code:
            # print(f'Deleting {additional_data_type} information on {word_id} OK: HTTP {response.status_code}')
            return True
        else:
            print(f'Failed deleting {additional_data_type} information on {word_id}: HTTP {response.status_code}')
            return False

    def process_page(self, page):
        processor = ENWiktionaryProcessor()
        processor.set_text(page.get())
        processor.set_title(page.title())
        for entry in processor.getall(fetch_additional_data=True, cleanup_definitions=True, advanced=True):
            entry_as_dict = entry.serialise()
            for additional_data_type, additional_data in entry_as_dict['additional_data'].items():
                word_id = self.get_word_id(entry)
                if word_id:
                    self.delete_all_additional_data_of_type(word_id, additional_data_type)
                    self.upload_additional_data(word_id, additional_data_type, additional_data)

    def run(self):
        threads = []
        counter = 0
        page_number = 0
        thread_batch_size = 300
        ct_time = time.time()
        for page in self.site.all_pages():
            # print(page_number)
            page_number += 1
            if self.page_number_to_resume_to > page_number:
                if not page_number % 10000:
                    print(f'>>> [{page_number}] ' + page.title() + ' <<< ')
                continue

            if not page_number % 250:
                print(f'>>> [{page_number}] ' + page.title() + ' <<< ')

            if page.namespace() != 0:
                continue

            thread = Thread(target=self.process_page, args=(page,))
            thread.start()
            threads.append(thread)
            counter += 1

            if len(threads) > thread_batch_size:
                for t in threads:
                    t.join(5)

                threads = []
                counter = 0
                throughput = 60 * thread_batch_size / (time.time() - ct_time)
                print(f'processing {throughput} pages/min...')
                ct_time = time.time()

        print(f'Job finished! {page_number} pages processed. ')


def main():
    parser = argparse.ArgumentParser(description='Import Wiktionary XML dump')
    parser.add_argument('--program', dest='program', action='store', help='Program name')
    parser.add_argument('--start-from-page', dest='start_page', action='store', help='Start from a certain page number.')

    args = parser.parse_args()
    Program = eval(f'{args.program}')
    bot = Program(args)
    bot.run()


if __name__ == '__main__':
    main()
