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
        assert 'reference' in out_entries[0].additional_data
        expected = "{{wikibolana|" + wiki + '|' + entry.entry + "}}"
        self.assertEqual(out_entries[0].additional_data['reference'][0], expected)

    def test_add_xlit_if_no_transcription(self):
        entry = Entry(
            entry='काम',
            part_of_speech='ana',
            definitions=['def1', 'def2'],
            language='hi',
        )
        function = postprocessors.add_xlit_if_no_transcription()
        function([entry])

    def test_add_language_ipa_if_not_exists(self):
        entry = Entry(
            entry='entry',
            part_of_speech='ana',
            definitions=['def1', 'def2'],
            language='hi',
        )
        function = postprocessors.add_language_ipa_if_not_exists()
        function([entry])

    def test_filter_out_languages(self):
        entry = Entry(
            entry='entry',
            part_of_speech='ana',
            definitions=['def1', 'def2'],
            language='en',
        )
        function = postprocessors.filter_out_languages('en')
        function([entry])
