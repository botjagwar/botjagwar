# coding: utf8

from modules import entryprocessor
from unittest.case import TestCase
from test_utils.mocks import PageMock, SiteMock



class TestFactory(TestCase):
    def test_factory_create_processor_french(self):
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create('fr')
        wiktionary_processor = wiktionary_processor_class()
        self.assertEqual(wiktionary_processor.__class__.__name__, 'FRWiktionaryProcessor')

    def test_factory_create_processor_english(self):
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create('en')
        wiktionary_processor = wiktionary_processor_class()
        self.assertEqual(wiktionary_processor.__class__.__name__, 'ENWiktionaryProcessor')

    def test_english_processor_getall(self):
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create('en')
        wiktionary_processor = wiktionary_processor_class()
        page = PageMock(SiteMock('en', 'wiktionary'), 'belief')
        wiktionary_processor.process(page)
        entries = wiktionary_processor.getall()
        self.assertEqual(entries[0], ('belief', 'ana', 'en', 'mental as true.'))

    def test_english_processor_retrieve_translations(self):
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create('en')
        wiktionary_processor = wiktionary_processor_class()
        page = PageMock(SiteMock('en', 'wiktionary'), 'belief')
        wiktionary_processor.process(page)
        entries = wiktionary_processor.retrieve_translations()
        for entry in entries:
            self.assertEqual(len(entry), 4)
            self.assertTrue(2 <= len(entry[2]) <= 7)

        self.assertEqual(entries[1], ('Glaube', 'ana', 'de', 'mental as true.'))
