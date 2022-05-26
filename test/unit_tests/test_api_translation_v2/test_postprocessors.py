from unittest import TestCase

from api.model.word import Entry
from api.translation_v2.functions import postprocessors


class TestPostProcessors(TestCase):
    def test_add_wiktionary_credit(self):
        wiki = 'mg'
        entry = Entry(
            entry='entry',
            part_of_speech='ana',
            definitions=['def1', 'def2'],
            language='en',
        )
        credit = postprocessors.add_wiktionary_credit(wiki)
        out_entries = credit([entry])
        assert hasattr(out_entries[0], 'reference')
        expected = "{{wikibolana|" + wiki + '|' + entry.entry + "}}"
        self.assertEquals(getattr(out_entries[0], 'reference'), expected)

    def test_add_xlit_if_no_transcription(self):
        postprocessors.add_xlit_if_no_transcription()

    def test_add_language_ipa_if_not_exists(self):
        postprocessors.add_language_ipa_if_not_exists()

    def test_filter_out_languages(self):
        postprocessors.filter_out_languages()

