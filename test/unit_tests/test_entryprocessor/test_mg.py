import unittest

from test_utils.mocks import PageMock, SiteMock
from . import GenericEntryProcessorTester


class TestMalagasyWiktionaryEntryprocessor(
    GenericEntryProcessorTester, unittest.TestCase
):
    def setUp(self):
        self.setup_for_language("mg", ["teny", "eau", "газета", "geloof"])

    def test_get_all_entries(self):
        super(TestMalagasyWiktionaryEntryprocessor, self).test_get_all_entries()

    def test_retrieve_translations(self):
        super(TestMalagasyWiktionaryEntryprocessor, self).test_retrieve_translations()

    def test_retrieve_translations_data_output(self):
        page = PageMock(SiteMock(self.language, "wiktionary"), "teny")
        self.processor.process(page)
        entries = self.processor.retrieve_translations()
        print(entries)
