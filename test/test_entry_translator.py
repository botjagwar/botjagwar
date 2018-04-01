# coding: utf8

import json
import requests
from subprocess import Popen
from subprocess import PIPE
from time import sleep
from test_utils.mocks import PageMock, SiteMock
from unittest.case import TestCase

from api.translation.core import Translation
from api.decorator import threaded, retry_on_fail


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


class TestEntryTranslatorProcessWiktionaryPage(TestCase):
    def setUp(self):
        self.launch_service()
        sleep(2.5)

    def tearDown(self):
        self.p2.kill()

    @threaded
    def launch_service(self):
        self.p2 = Popen(["python3.6", "dictionary_service.py", "--db-file", '/tmp/test.db'])

    def test_process_wiktionary_page_english(self):
        for pagename in LIST:
            translation = Translation()
            page = PageMock(SiteMock('en', 'wiktionary'), pagename)
            translation.process_wiktionary_wiki_page(page)

    def test_process_wiktionary_page_french(self):
        for pagename in LIST:
            translation = Translation()
            page = PageMock(SiteMock('fr', 'wiktionary'), pagename)
            translation.process_wiktionary_wiki_page(page)


class TestEntryTranslatorServices(TestCase):
    def setUp(self):
        self.launch_service()
        sleep(2.5)

    def tearDown(self):
        self.p2.kill()

    @threaded
    def launch_service(self):
        self.p2 = Popen(["python3.6", "entry_translator.py", "&"])

    def check_response_status(self, url, data):
        resp = requests.put(url, json=data)
        resp_data = json.loads(resp.text) if resp.text else {}
        self.assertEqual(resp.status_code, 200)
        for _, added_entries in list(resp_data.items()):
            self.assertTrue(isinstance(added_entries, list))

    @retry_on_fail(Exception, retries=10, time_between_retries=.5)
    def test_translate_english_word(self):
        data = {
            "dryrun": True,
            "word": "rice",
            "translation": "vary",
            "POS": "ana",
        }
        url = "http://localhost:8000/translate/en"
        self.check_response_status(url, data)

    @retry_on_fail(Exception, retries=10, time_between_retries=.5)
    def test_translate_french_word(self):
        data = {
            "dryrun": True,
            "word": "riz",
            "translation": "vary",
            "POS": "ana",
        }
        url = "http://localhost:8000/translate/fr"
        self.check_response_status(url, data)
