from api.entryprocessor import WiktionaryProcessorFactory
from api.model.word import Entry
from test_utils.mocks import PageMock, SiteMock


class GenericEntryProcessorTester:
    def setup_for_language(self, language, test_pages=list()):
        self.language = language
        self.test_pages = test_pages
        test_class = WiktionaryProcessorFactory.create(language)
        self.processor = test_class()

    def test_get_all_entries(self):
        for page_names in self.test_pages:
            page = PageMock(SiteMock(self.language, 'wiktionary'), page_names)
            self.content = page.get()
            self.processor.set_text(self.content)
            self.processor.process(page)
            entries = self.processor.get_all_entries()
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
