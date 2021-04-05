import unittest

from test_utils.mocks import PageMock, SiteMock
from . import GenericEntryProcessorTester


class TestEnglishWiktionaryEntryprocessor(GenericEntryProcessorTester, unittest.TestCase):
    def setUp(self):
        self.setup_for_language('en', ['eau', 'air', 'газета', 'geloof'])

    def test_getall(self):
        super(TestEnglishWiktionaryEntryprocessor, self).test_getall()

    def test_retrieve_translations(self):
        super(TestEnglishWiktionaryEntryprocessor, self).test_retrieve_translations()

    def test_retrieve_translations_data_output(self):
        page = PageMock(SiteMock(self.language, 'wiktionary'), 'air')
        self.processor.process(page)
        entries = self.processor.retrieve_translations()
        entry = [e for e in entries if e.language == 'ko'][-1]
        word, pos, lang, definition  = entry.entry, entry.part_of_speech, entry.language, entry.entry_definition
        self.assertIn(word, ['공기', '空氣'])
        self.assertEqual(pos, 'ana')
        self.assertEqual(lang, 'ko')
        self.assertEqual(definition[0], "air")
