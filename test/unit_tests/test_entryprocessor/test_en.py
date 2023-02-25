import unittest

from test_utils.mocks import PageMock, SiteMock
from . import GenericEntryProcessorTester


class TestEnglishWiktionaryEntryprocessor(
        GenericEntryProcessorTester,
        unittest.TestCase):
    def setUp(self):
        self.setup_for_language('en', ['eau', 'air', 'газета', 'geloof'])

    def test_get_all_entries(self):
        super(TestEnglishWiktionaryEntryprocessor, self).test_get_all_entries()

    def test_retrieve_translations(self):
        super(TestEnglishWiktionaryEntryprocessor,
              self).test_retrieve_translations()

    def test_retrieve_translations_data_output(self):
        page = PageMock(SiteMock(self.language, 'wiktionary'), 'air')
        self.processor.process(page)
        translations = self.processor.retrieve_translations()
        entries = [e for e in translations if e.language == 'ko']
        self.assertNotEqual(len(entries), 0, "No entries were found")
        entry = entries[0]
        word, pos, lang, definition = entry.word, entry.part_of_speech, entry.language, entry.definition
        self.assertIn(word, ['공기', '空氣'])
        self.assertEqual(pos, 'ana')
        self.assertEqual(lang, 'ko')
        self.assertEqual(definition, "mixture of gases making up the atmosphere of the Earth")
