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

from api.decorator import threaded, retry_on_fail
from api.translation.core import Translation
from test_utils.mocks import PageMock, SiteMock

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
