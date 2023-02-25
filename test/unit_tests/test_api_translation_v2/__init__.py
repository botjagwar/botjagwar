from unittest.case import TestCase
from unittest.mock import MagicMock

from parameterized import parameterized

from api.model.word import Entry
from api.translation_v2.core import Translation


class TestPostprocessors(TestCase):
    def test_add_language_ipa_if_not_exists(self):
        pass

    def test_add_xlit_if_no_transcription(self):
        pass


class TestDefinitions(TestCase):
    def test_translate_form_of_templates(self):
        pass

    def test_translate_using_postgrest_json_dictionary(self):
        pass

    def test_translate_using_convergent_definition(self):
        pass

    def test_translate_using_bridge_language(self):
        pass


class TestReferences(TestCase):
    def test_translate_reference_templates(self):
        pass

    def test_translate_references(self):
        pass


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

    @parameterized.expand([(True,), (False,)])
    def test_generate_summary(self, exists):
        page_mock = MagicMock()
        page_mock.exists.return_value = exists
        page_mock.isRedirectPage.return_value = False
        content = """{{jereo|fan-an'|fan-an-|fana-n'|fana-n-|fanan'|fanan-}}
== {{=sv=}} ==
{{-e-ana-|sv}}
'''fanan''' {{fanononana X-SAMPA||sv}} {{fanononana||sv}}
# Endriky ny teny [[fana]]
        """
        if page_mock.exists():
            page_mock.get.return_value = content

        summary = Translation().generate_summary(
            [self.entry1, self.entry2, self.entry3],
            target_page=page_mock,
            content=content
        )
        # if not page_mock.exists():
        #     self.assertIn(self.entry1.language, summary)
        #     self.assertIn(self.entry2.language, summary)
        #     self.assertIn(self.entry3.language, summary)
        # else:
        #     self.assertEqual(summary, 'nanitsy')

    def test_add_credit_no_reference(self):
        wikipage = MagicMock()
        wikipage.title.return_value = 'test'
        wikipage.site.language = 'en'
        entries = Translation.add_wiktionary_credit([self.entry1, self.entry2], wikipage)
        print(entries)
        assert 'reference' in entries[0].additional_data
        assert 'reference' in entries[1].additional_data

    def test_aggregate_entry_data(self):
        pass

    def test_run_static_postprocessors(self):
        pass

    def test_run_dynamic_postprocessors(self):
        pass

    def test_translate_wiktionary_page(self):
        pass

    def test_create_lemma_if_not_exists(self):
        pass

    def test_publish_to_wiktionary(self):
        pass
