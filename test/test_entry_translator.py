# coding: utf8
import asyncio
import json
import os
from subprocess import PIPE
from subprocess import Popen
from time import sleep
from unittest.case import TestCase

import aiohttp
import requests

import api.translation.core
from api import entryprocessor
from api.decorator import threaded, retry_on_fail
from api.translation.core import Translation
from test_utils.mocks import PageMock, SiteMock

#Monkey-patching pywikibot API calls:
api.translation.core.pwbot.Page = PageMock
api.translation.core.pwbot.Site = SiteMock
api.translation.core.LANGUAGE_BLACKLIST = []

LIST = [
    'eau',
    'air',
    'èstre',
    'газета',
    'газет',
    'geloof',
    'belief',
    'peel',
    '合宿',
    'heel',
    '百萬',
    'peigne',
    'pagne',
]

DB_PATH = '/tmp/test.db'
URL_HEAD = 'http://localhost:8001'
DICTIONARY_SERVICE = None


class TestEntryTranslatorProcessWiktionaryPage(TestCase):

    def setUp(self):
        self.launch_service()
        self.wait_until_ready()

    def tearDown(self):
        self.kill_service()
        sleep(.4)

    @staticmethod
    @threaded
    def launch_service():
        global DICTIONARY_SERVICE
        DICTIONARY_SERVICE = Popen(["python3.6", "dictionary_service.py", '--db-file', DB_PATH, "-p", '8001'],
                                   stdin=PIPE, stdout=PIPE, stderr=PIPE)
        DICTIONARY_SERVICE.communicate()

    @retry_on_fail([Exception], retries=10, time_between_retries=.4)
    def wait_until_ready(self):
        resp = requests.get(URL_HEAD + '/ping')
        assert resp.status_code == 200

    @staticmethod
    def kill_service():
        DICTIONARY_SERVICE.kill()
        os.system('rm %s' % DB_PATH)

    def test_fr_process_entry_in_native_language(self):
        loop = asyncio.get_event_loop()

        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            async def translation_mock(x, y):
                return [{"definition": "araotra"}]
            translation = Translation()
            translation.translate_word = translation_mock
            page = PageMock(SiteMock('fr', 'wiktionary'), 'peigne')
            translation.process_wiktionary_wiki_page(page)
            fr_entries = [e for e in translation.process_entry_in_native_language(page.get(), page.title(), 'fr', [])
                          if e.language == 'fr']
            for e in fr_entries:
                self.assertEqual(e.entry, 'peigne')
                self.assertEqual(e.language, 'fr')
                self.assertEqual(e.part_of_speech, 'ana')

        loop.run_until_complete(_wrapped_test())

    def test_fr_process_entry_in_foreign_language(self):
        loop = asyncio.get_event_loop()

        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            def translation_mock(x, y):
                return [{"definition": "misy"}]
            translation = Translation()
            translation.translate_word = translation_mock
            page = PageMock(SiteMock('fr', 'wiktionary'), 'èstre')
            wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create('fr')
            wiktionary_processor = wiktionary_processor_class()
            wiktionary_processor.process(page)
            entry = [e for e in wiktionary_processor.getall()
                     if e.language == 'oc'][0]
            info = translation.process_entry_in_foreign_language(
                entry, page.get(), 'fr', [])
            self.assertEqual(info.entry, 'èstre')
            self.assertEqual(info.language, 'oc')
            self.assertEqual(info.part_of_speech, 'mat')

        loop.run_until_complete(_wrapped_test())

    def test_en_process_entry_in_native_language(self):
        loop = asyncio.get_event_loop()

        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            def translation_mock(x, y):
                return [{"definition": "vody tongotra"}]
            translation = Translation()
            translation.translate_word = translation_mock
            page = PageMock(SiteMock('en', 'wiktionary'), 'heel')
            translation.process_wiktionary_wiki_page(page)
            fr_entries = [e for e in translation.process_entry_in_native_language(page.get(), page.title(), 'en', [])
                          if e.language == 'en']
            for e in fr_entries:
                self.assertEqual(e.entry, 'peigne')
                self.assertEqual(e.language, 'en')
                self.assertEqual(e.part_of_speech, 'ana')

        loop.run_until_complete(_wrapped_test())

    def test_en_process_entry_in_foreign_language(self):
        loop = asyncio.get_event_loop()

        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            def translation_mock(x, y):
                return [{"definition": "misy"}]
            translation = Translation()
            translation.translate_word = translation_mock
            page = PageMock(SiteMock('en', 'wiktionary'), 'pagne')
            wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create('en')
            wiktionary_processor = wiktionary_processor_class()
            wiktionary_processor.process(page)
            print(wiktionary_processor.getall())
            entry = [e for e in wiktionary_processor.getall()
                     if e.language == 'fr'][0]
            info = translation.process_entry_in_foreign_language(
                entry, page.get(), 'en', [])
            self.assertEqual(info.entry, 'pagne')
            self.assertEqual(info.language, 'fr')
            self.assertEqual(info.part_of_speech, 'ana')

        loop.run_until_complete(_wrapped_test())

    def test_process_wiktionary_page_english(self):

        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            loop = asyncio.get_event_loop()
            for pagename in LIST:
                translation = Translation()
                page = PageMock(SiteMock('en', 'wiktionary'), pagename)
                loop.run_until_complete(translation.process_wiktionary_wiki_page(page))
        _wrapped_test()

    def test_process_wiktionary_page_french(self):
        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            loop = asyncio.get_event_loop()
            for pagename in LIST:
                translation = Translation()
                page = PageMock(SiteMock('fr', 'wiktionary'), pagename)
                loop.run_until_complete(translation.process_wiktionary_wiki_page(page))
        _wrapped_test()


class TestEntryTranslatorServices(TestCase):
    def setUp(self):
        self.launch_service()
        sleep(2.5)

    def tearDown(self):
        self.p2.kill()

    @threaded
    def launch_service(self):
        self.p2 = Popen(["python3.6", "entry_translator.py", "-p", '8000'])

    @retry_on_fail([Exception], retries=10, time_between_retries=.4)
    def check_response_status(self, url, data):
        resp = requests.put(url, json=data)
        resp_data = json.loads(resp.text) if resp.text else {}
        self.assertEqual(resp.status_code, 200)
        for _, added_entries in list(resp_data.items()):
            self.assertTrue(isinstance(added_entries, list))

    def test_translate_english_word(self):
        data = {
            "dryrun": True,
            "word": "rice",
            "translation": "vary",
            "POS": "ana",
        }
        url = "http://localhost:8000/translate/en"
        self.check_response_status(url, data)

    def test_translate_french_word(self):
        data = {
            "dryrun": True,
            "word": "riz",
            "translation": "vary",
            "POS": "ana",
        }
        url = "http://localhost:8000/translate/fr"
        self.check_response_status(url, data)
