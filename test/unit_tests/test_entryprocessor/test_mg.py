import unittest

from api.entryprocessor.wiki.mg import MGWiktionaryProcessor
from test_utils.mocks import PageMock, SiteMock
from . import GenericEntryProcessorTester


class TestMalagasyWiktionaryEntryprocessor(
    GenericEntryProcessorTester, unittest.TestCase
):
    def setUp(self):
        self.setup_for_language("mg", ["teny", "eau", "газета", "geloof"])

    # def test_get_all_entries(self):
    #     super(TestMalagasyWiktionaryEntryprocessor, self).test_get_all_entries()

    def test_retrieve_translations(self):
        super(TestMalagasyWiktionaryEntryprocessor, self).test_retrieve_translations()

    def test_retrieve_translations_data_output(self):
        page = PageMock(SiteMock(self.language, "wiktionary"), "teny")
        self.processor.process(page)
        entries = self.processor.retrieve_translations()
        print(entries)

    def test_get_all_entries_keeps_pos_definitions_separate(self) -> None:
        processor = MGWiktionaryProcessor()
        processor.set_title("halin")
        processor.set_text(
            """=={{=ca=}}==
{{-mat-|ca}}
# mifindra any amin'ny toerana hafa
{{-e-mat-|ca}}
# endriky ny matoanteny halar
{{-ana-|ca}}
# fidiram-bola azo tamin'ny fivarotana
"""
        )

        entries = processor.get_all_entries()

        assert [entry.part_of_speech for entry in entries] == ["mat", "e-mat", "ana"]
        assert [entry.definitions for entry in entries] == [
            ["mifindra any amin'ny toerana hafa"],
            ["endriky ny matoanteny halar"],
            ["fidiram-bola azo tamin'ny fivarotana"],
        ]

    def test_get_all_entries_uses_each_repeated_marker_position(self) -> None:
        processor = MGWiktionaryProcessor()
        processor.set_title("teny")
        processor.set_text("{{-ana-|mg}}\n# voalohany\n{{-ana-|mg}}\n# faharoa")

        entries = processor.get_all_entries()

        assert [entry.definitions for entry in entries] == [["voalohany"], ["faharoa"]]
