import unittest
from test_utils.mocks import PageMock, SiteMock
from api.entryprocessor import WiktionaryProcessorFactory


class GenericEntryProcessorTester:
    def setup_for_language(self, language, test_pages=[]):
        self.language = language
        self.test_pages = test_pages
        test_class = WiktionaryProcessorFactory.create(language)
        self.processor = test_class()

    def test_getall(self):
        for page_names in self.test_pages:
            page = PageMock(SiteMock(self.language, 'wiktionary'), page_names)
            self.content = page.get()
            self.processor.set_text(self.content)
            self.processor.process(page)
            entries = self.processor.getall()
            assert isinstance(entries, list)
            for t in entries:
                assert len(t) == 4

    def test_retrieve_translations(self):
        for page_names in self.test_pages:
            page = PageMock(SiteMock(self.language, 'wiktionary'), page_names)
            self.processor.process(page)
            entries = self.processor.retrieve_translations()
            assert isinstance(entries, list)
            for t in entries:
                assert len(t) == 4


class TestEnglishWiktionaryEntryprocessor(GenericEntryProcessorTester, unittest.TestCase):
    def setUp(self):
        self.setup_for_language('en', ['eau', 'air', 'газета', 'geloof'])

    def test_retrieve_translations_data_output(self):
        page = PageMock(SiteMock(self.language, 'wiktionary'), 'air')
        self.processor.process(page)
        entries = self.processor.retrieve_translations()
        entry = entries[-1]
        word, pos, lang, definition = entry
        self.assertEqual(word, '공기')
        self.assertEqual(pos, 'mat')
        self.assertEqual(lang, 'ko')
        self.assertEqual(definition, "The substance constituting earth's atmosphere")


class TestFrenchWiktionaryEntryprocessor(GenericEntryProcessorTester, unittest.TestCase):
    def setUp(self):
        self.setup_for_language('fr', ['eau', 'air', 'газета', 'geloof'])

    def test_retrieve_translations_data_output(self):
        page = PageMock(SiteMock(self.language, 'wiktionary'), 'air')
        self.processor.process(page)
        entries = self.processor.retrieve_translations()
        entry = entries[-1]
        word, pos, lang, definition = entry
        self.assertEqual(word, '공기')
        self.assertEqual(pos, 'ana')
        self.assertEqual(lang, 'ko')
        self.assertTrue(definition.startswith('mélange'))
