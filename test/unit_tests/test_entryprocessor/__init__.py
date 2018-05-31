from api.entryprocessor import WiktionaryProcessorFactory
from object_model.word import Entry
from test_utils.mocks import PageMock, SiteMock


class GenericEntryProcessorTester:
    def setup_for_language(self, language, test_pages=list()):
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
            assert isinstance(entries, list), entries
            for e in entries:
                assert isinstance(e, Entry)

    def test_retrieve_translations(self):
        for page_names in self.test_pages:
            page = PageMock(SiteMock(self.language, 'wiktionary'), page_names)
            self.processor.process(page)
            entries = self.processor.retrieve_translations()
            assert isinstance(entries, list), entries
            for e in entries:
                assert isinstance(e, Entry)

#
# class TestMalagasyWiktionaryEntryprocessor(GenericEntryProcessorTester, unittest.TestCase):
#     def setUp(self):
#         self.setup_for_language('mg', ['rano', 'air', 'газета', 'geloof'])
#
#     def test_retrieve_translations_data_output(self):
#         page = PageMock(SiteMock(self.language, 'wiktionary'), 'rano')
#         self.processor.process(page)
#         entries = self.processor.retrieve_translations()
#         entry = entries[-1]
#         word, pos, lang, definition = entry
#         self.assertEqual(word, '공기')
#         self.assertEqual(pos, 'ana')
#         self.assertEqual(lang, 'ko')
#         self.assertTrue(definition.startswith('mélange'))
