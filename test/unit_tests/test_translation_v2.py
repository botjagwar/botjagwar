from unittest.case import TestCase
from unittest.mock import MagicMock

from api.model.word import Entry
from api.translation_v2.core import Translation


class TestTranslationV2(TestCase):
    def setUp(self) -> None:
        self.entry1 = Entry(
            entry='test1',
            language='l1',
            part_of_speech='ana',
            definitions=[
                'def1-1',
                'def2-1'])
        self.entry2 = Entry(
            entry='test2',
            language='l2',
            part_of_speech='ana',
            definitions=[
                'def2-2',
                'def2-2'])
        self.entry3 = Entry(
            entry='test3',
            language='l3',
            part_of_speech='ana',
            definitions=[
                'def3-3',
                'def2-3'])

    def tearDown(self) -> None:
        pass

    def test_generate_summary(self):
        summary = Translation().generate_summary(
            [self.entry1, self.entry2, self.entry3])
        self.assertIn(self.entry1.language, summary)
        self.assertIn(self.entry2.language, summary)
        self.assertIn(self.entry3.language, summary)

    def test_add_credit_no_reference(self):
        wikipage = MagicMock()
        wikipage.title.return_value = 'test'
        wikipage.site.language = 'en'
        entries = Translation.add_wiktionary_credit(
            [self.entry1, self.entry2], wikipage)
        assert hasattr(entries[0], 'reference')
        assert hasattr(entries[1], 'reference')
