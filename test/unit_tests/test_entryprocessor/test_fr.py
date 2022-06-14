import unittest

from test_utils.mocks import PageMock, SiteMock
from . import GenericEntryProcessorTester


class TestFrenchWiktionaryEntryprocessor(
        GenericEntryProcessorTester,
        unittest.TestCase):
    def setUp(self):
        self.setup_for_language('fr', ['eau', 'air', 'газета', 'geloof'])

    def test_get_all_entries(self):
        super(TestFrenchWiktionaryEntryprocessor, self).test_get_all_entries()

    def test_retrieve_translations(self):
        super(TestFrenchWiktionaryEntryprocessor,
              self).test_retrieve_translations()

    def test_retrieve_translations_data_output(self):
        page = PageMock(SiteMock(self.language, 'wiktionary'), 'air')
        self.processor.process(page)
        entries = self.processor.retrieve_translations()
        entry = [e for e in entries if e.language == 'ko'][0]
        word, pos, lang, definition = entry.entry, entry.part_of_speech, entry.language, entry.definitions
        self.assertEqual(word, '공기')
        self.assertEqual(pos, 'ana')
        self.assertEqual(lang, 'ko')
        self.assertEqual(definition[0], 'air')
