from unittest.case import TestCase
from unittest.mock import MagicMock

from api.model.word import Entry
from api.translation_v2.core import Translation


class TestPostprocessors(TestCase):
    def test_add_language_ipa_if_not_exists(self):
        raise AssertionError()

    def test_add_xlit_if_no_transcription(self):
        raise AssertionError()


class TestDefinitions(TestCase):
    def test_translate_form_of_templates(self):
        raise AssertionError()

    def test_translate_using_postgrest_json_dictionary(self):
        raise AssertionError()

    def test_translate_using_convergent_definition(self):
        raise AssertionError()

    def test_translate_using_bridge_language(self):
        raise AssertionError()


class TestReferences(TestCase):
    def test_translate_reference_templates(self):
        raise AssertionError()

    def test_translate_references(self):
        raise AssertionError()


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

    def test_aggregate_entry_data(self):
        raise AssertionError()

    def test_run_static_postprocessors(self):
        raise AssertionError()

    def test_run_dynamic_postprocessors(self):
        raise AssertionError()

    def test_translate_wiktionary_page(self):
        raise AssertionError()

    def test_create_lemma_if_not_exists(self):
        raise AssertionError()

    def test_publish_to_wiktionary(self):
        raise AssertionError()
