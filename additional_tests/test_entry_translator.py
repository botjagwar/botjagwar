# coding: utf8
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

# Monkey-patching pywikibot API calls:
# api.translation.core.pwbot.Page = PageMock
# api.translation.core.pwbot.Site = SiteMock
api.translation.core.LANGUAGE_BLACKLIST = []

LIST = [
    "eau",
    "air",
    "èstre",
    "газета",
    "газет",
    "geloof",
    "belief",
    "peel",
    "合宿",
    "heel",
    "百萬",
    "peigne",
    "pagne",
]

EN_PAGE_CONTENT = """
==English==
[[File:Tissus au pagne.JPG|thumb|Pagnes]]
[[File:Pagne KITA 01.jpg|thumb|Men and women wearing pagnes]]

===Etymology===
Borrowed from {{bor|en|fr|pagne}}.

===Noun===
{{en-noun}}

# A length of wax-print [[fabric]] made in [[West Africa]], worn as a single wrap or made into other [[clothing]], and serving as a form of [[currency]].
#* {{quote-book|en|year=1997 |title=A Modern Economic History of Africa: The nineteenth century|author=Paul Tiyambe Zeleza |page=286 |ISBN=996646025X |passage=In Senegal the local cloth currency, '''pagne''', made of tama, or strips, was increasingly supplemented by French imported indigo-dyed cloth from India called guinee . The guinee was used as currency in lower Senegal. In upper Senegal it became a larger unit equivalent to a number of '''pagnes'''. The exchange rate between guinee, '''pagnes''', and francs became more complicated from the 1830s as a result of excessive imports of guinees and francs. }}
#* {{quote-book|en|year=1998 |title=Possession, Ecstasy, and Law in Ewe Voodoo|author=Judy Rosenthal |page=204 |ISBN=0813918057 |passage=If a woman wears her sister's '''pagne''' [cloth] to go and have sexual intercourse with a man, she has committed afodegbe. This happened to the wife of a sofo recently. She took her sister's '''pagne''', went and stayed with her husband, and then took the '''pagne''' back to her sister. As her sister's husband [the husband of the woman who took the '''pagne'''] is a sofo, the vodu caught her sister [the woman whose '''pagne''' was taken] right away. She was ill. }}
#* {{quote-book|en|year=2011 |title=Monique and the Mango Rains|author=Kris Holloway |page= |ISBN=1851688897 |passage=When young girls are first learning how to wear a '''pagne''', sometimes we sew straps onto the corners so the '''pagne''' can be tied and doesn't fall down if they don't wrap it right. }}
#* {{quote-book|en|year=2016 |title=Patterns in Circulation: Cloth, Gender, and Materiality in West Africa|author=Nina Sylvanus |page= 2 |ISBN=022639736X |passage='''Pagne''' is part of the transfer of wealth from a prospective groom to his intended wife prior to marriage or the inheritance a woman leaves for her daughters. }}

===Anagrams===
* {{anagrams|en|a=aegnp|pegan}}

----

==French==

===Pronunciation===
* {{fr-IPA}}
* {{rhymes|fr|aɲ}}

===Etymology 1===
Borrowed from {{bor|fr|es|paño}}, from {{etyl|la|fr}} {{m|la|pannus}}. {{doublet|fr|pan}}.

====Noun====
{{fr-noun|m}}

# [[loincloth]]
#* '''2001''', Hervé Beaumont, ''Égypte. Le guide des civilisations égyptiennes, des pharaons à l'islam;'', Editions Marcus, 213.
#*: Statue en calcaire de Ranofrê portant la perruque et un '''pagne''' court, provenant du mastaba de Ti à Saqqara.
#*: Limestone statue of Ranofre wearing the wig and a short '''loincloth''', originating from the mastaba of Ti at Saqqara.
# [[grass skirt]]

===Etymology 2===
From {{cog|fr|panier}}.

====Noun====
{{fr-noun|m}}

# [[bed]]

===Further reading===
* {{R:TLFi}}

[[Category:fr:Clothing]]
"""

FR_PAGE_CONTENT = """
{{voir|estre}}

== {{langue|oc}} ==
=== {{S|étymologie}} ===
: {{ébauche-étym|oc}}

=== {{S|verbe|oc}} ===
'''èstre''' {{pron||oc}} {{oc-norme classique}}
# [[être|Être]].

==== {{S|variantes}} ====
* [[èsser#oc|èsser]]

==== {{S|variantes dialectales}} ====
* [[èster#oc|èster]] {{oc aranais|nocat=1}}

=== {{S|références}} ===
* {{R:Cantalausa}}

{{clé de tri|estre}}

"""

DB_PATH = "/tmp/test.db"
URL_HEAD = "http://localhost:8001"
DICTIONARY_SERVICE = None


class TestEntryTranslatorProcessWiktionaryPage(TestCase):

    def setUp(self):
        self.launch_service()
        self.wait_until_ready()

    def tearDown(self):
        self.kill_service()
        sleep(0.4)

    @staticmethod
    @threaded
    def launch_service():
        global DICTIONARY_SERVICE
        DICTIONARY_SERVICE = Popen(
            ["python3", "dictionary_service.py", "--db-file", DB_PATH, "-p", "8001"],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
        )
        DICTIONARY_SERVICE.communicate()

    @retry_on_fail([Exception], retries=10, time_between_retries=0.4)
    def wait_until_ready(self):
        resp = requests.get(URL_HEAD + "/ping")
        assert resp.status_code == 200

    @staticmethod
    def kill_service():
        DICTIONARY_SERVICE.kill()
        os.system("rm %s" % DB_PATH)

    def test_fr_process_entry_in_native_language(self):
        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            def translation_mock(x, y):
                return [
                    {"part_of_speech": "ana", "definition": "araotra"},
                    {"part_of_speech": "ana", "definition": "araotra"},
                ]

            translation = Translation()
            translation.translate_word = translation_mock
            page = PageMock(SiteMock("fr", "wiktionary"), "peigne")
            translation.process_wiktionary_wiki_page(page)
            fr_entries = [
                e
                for e in translation.process_entry_in_native_language(
                    page.get(), page.title(), "fr", []
                )
                if e.language == "fr"
            ]
            for e in fr_entries:
                self.assertEqual(e.entry, "peigne")
                self.assertEqual(e.language, "fr")
                self.assertEqual(e.part_of_speech, "ana")

        _wrapped_test()

    def test_fr_process_entry_in_foreign_language(self):
        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            def translation_mock(x, y):
                return [
                    {"definition": "misy", "part_of_speech": "mat"},
                    {"part_of_speech": "ana", "definition": "araotra"},
                ]

            translation = Translation()
            translation.translate_word = translation_mock
            page = PageMock(SiteMock("fr", "wiktionary"), "èstre")
            wiktionary_processor_class = (
                entryprocessor.WiktionaryProcessorFactory.create("fr")
            )
            wiktionary_processor = wiktionary_processor_class()
            wiktionary_processor.process(page)
            entry = [
                e for e in wiktionary_processor.get_all_entries() if e.language == "oc"
            ][0]
            info = translation.process_entry_in_foreign_language(
                entry, page.title(), "fr", []
            )
            self.assertEqual(info.entry, "èstre")
            self.assertEqual(info.language, "oc")
            self.assertEqual(info.part_of_speech, "mat")

        _wrapped_test()

    def test_en_process_entry_in_native_language(self):
        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            def translation_mock(x, y):
                return [
                    {"definition": "vody tongotra", "part_of_speech": "ana"},
                    {"part_of_speech": "ana", "definition": "araotra"},
                ]

            translation = Translation()
            translation.translate_word = translation_mock
            page = PageMock(SiteMock("en", "wiktionary"), "heel")
            translation.process_wiktionary_wiki_page(page)
            fr_entries = [
                e
                for e in translation.process_entry_in_native_language(
                    page.get(), page.title(), "en", []
                )
                if e.language == "en"
            ]
            for e in fr_entries:
                self.assertEqual(e.entry, "peigne")
                self.assertEqual(e.language, "en")
                self.assertEqual(e.part_of_speech, "ana")

        _wrapped_test()

    def test_en_process_entry_in_foreign_language(self):
        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            def translation_mock(x, y):
                return [
                    {"definition": "misy", "part_of_speech": "mat"},
                    {"definition": "salaka", "part_of_speech": "ana"},
                ]

            def page_content_mock():
                return EN_PAGE_CONTENT

            def page_title_mock():
                return "pagne"

            translation = Translation()
            translation.translate_word = translation_mock
            page = PageMock(SiteMock("en", "wiktionary"), "pagne")
            page.title = page_title_mock
            page.get = page_content_mock
            wiktionary_processor_class = (
                entryprocessor.WiktionaryProcessorFactory.create("en")
            )
            wiktionary_processor = wiktionary_processor_class()
            wiktionary_processor.process(page)
            print(wiktionary_processor.get_all_entries())
            entry = [
                e for e in wiktionary_processor.get_all_entries() if e.language == "fr"
            ][0]
            info = translation.process_entry_in_foreign_language(
                entry, page.title(), "en", []
            )
            self.assertEqual(info.entry, "pagne")
            self.assertEqual(info.language, "fr")
            self.assertEqual(info.part_of_speech, "ana")

        _wrapped_test()

    def test_process_wiktionary_page_english(self):
        def page_content_mock():
            return EN_PAGE_CONTENT

        def page_title_mock():
            return "pagne"

        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            for pagename in LIST:
                translation = Translation()
                page = PageMock(SiteMock("en", "wiktionary"), pagename)
                page.get = page_content_mock
                page.title = page_title_mock
                translation.process_wiktionary_wiki_page(page)

        _wrapped_test()

    def test_process_wiktionary_page_french(self):
        @retry_on_fail([aiohttp.client_exceptions.ClientConnectionError])
        def _wrapped_test():
            for pagename in LIST:
                translation = Translation()
                page = PageMock(SiteMock("fr", "wiktionary"), pagename)
                translation.process_wiktionary_wiki_page(page)

        _wrapped_test()


class TestEntryTranslatorServices(TestCase):
    def setUp(self):
        self.launch_service()
        sleep(2.5)

    def tearDown(self):
        self.p2.kill()

    @threaded
    def launch_service(self):
        self.p2 = Popen(["python3", "entry_translator.py", "-p", "8000"])

    @retry_on_fail([Exception], retries=10, time_between_retries=0.4)
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
