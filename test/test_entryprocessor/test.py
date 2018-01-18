# coding: utf8

from modules import entryprocessor
from unittest.case import TestCase
from test_utils.mocks import PageMock, SiteMock



class TestFactory(TestCase):
    def test_factory_create_processor_french(self):
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create('fr')
        wiktionary_processor = wiktionary_processor_class()
        self.assertEquals(wiktionary_processor.__class__.__name__, 'FRWiktionaryProcessor')

    def test_factory_create_processor_english(self):
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create('en')
        wiktionary_processor = wiktionary_processor_class()
        self.assertEquals(wiktionary_processor.__class__.__name__, 'ENWiktionaryProcessor')

    def test_english_processor_getall(self):
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create('en')
        wiktionary_processor = wiktionary_processor_class()
        page = PageMock(SiteMock('en', 'wiktionary'), u'belief')
        wiktionary_processor.process(page)
        entries = wiktionary_processor.getall()
        self.assertEquals(entries[0], (u'belief', 'ana', 'en', u'mental as true.'))

    def test_english_processor_retrieve_translations(self):
        wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create('en')
        wiktionary_processor = wiktionary_processor_class()
        page = PageMock(SiteMock('en', 'wiktionary'), u'belief')
        wiktionary_processor.process(page)
        entries = wiktionary_processor.retrieve_translations()
        for entry in entries:
            self.assertEquals(entry, 4)
            self.assertTrue(2 <= len(entry[2]) <= 7)

        self.assertEquals(entries[1], (u'Glaube', 'ana', u'de', u'mental as true.'))
