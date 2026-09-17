from unittest import TestCase
from unittest.mock import MagicMock

from api.translation_v2.functions import references

references.TemplateTranslation = MagicMock()
postgrest = MagicMock()
references.TemplateTranslation.return_value = postgrest


class TestReferencesTranslator(TestCase):
    def test_translate_R_is_mapped(self):
        ref = "{{R:Translated|toto titi tata}}"
        postgrest.get_mapped_template_in_database = MagicMock()
        postgrest.get_mapped_template_in_database.return_value = None
        references.translate_reference_templates(ref, "en", "mg")

    def test_translate_references_is_mapped(self):
        ref = "{{R:Translated|toto titi tata}}"
        postgrest.get_mapped_template_in_database = MagicMock()
        postgrest.get_mapped_template_in_database.return_value = "Tsiahy:Voadika"
        references.translate_references([ref], "en", "mg")

    def test_translate_references_is_not_mapped(self):
        ref = "{{cite-web|toto titi tata}}"
        postgrest.get_mapped_template_in_database = MagicMock()
        postgrest.get_mapped_template_in_database.return_value = None
        references.translate_references([ref], "en", "mg")

    def test_unmapped_R_references_are_preserved(self):
        refs = ["{{R|rif|Serhoual:2002}}", "{{R|rif|Abarrou:2024}}"]
        postgrest.get_mapped_template_in_database = MagicMock(return_value=None)

        translated_refs = references.translate_references(refs, "en", "mg")

        self.assertEqual(translated_refs, refs)

    def test_tsiahy_localizes_date_and_preserves_title_and_pages(self):
        ref = (
            "{{R:Book|title=Cien años de soledad (R:Book)|date=December 28, 2007"
            "|page=42|pages=45–47}}"
        )
        postgrest.get_mapped_template_in_database = MagicMock(return_value=None)

        translated = references.translate_reference_templates(ref, "en", "mg")

        self.assertEqual(
            translated,
            "{{Tsiahy:Book|title=Cien años de soledad (R:Book)|date=28 Desambra 2007"
            "|page=42|pages=45–47}}",
        )

    def test_invalid_date_is_preserved(self):
        ref = "{{R:Book|date=February 31, 2020}}"
        postgrest.get_mapped_template_in_database = MagicMock(return_value=None)

        translated = references.translate_reference_templates(ref, "en", "mg")

        self.assertEqual(translated, "{{Tsiahy:Book|date=February 31, 2020}}")

    def test_cite_template_localizes_date_without_renaming(self):
        ref = "{{cite-web|title=Original title|date=2018-05-05|page=7}}"

        translated = references.translate_reference_templates(ref, "en", "mg")

        self.assertEqual(
            translated,
            "{{cite-web|title=Original title|date=5 Mey 2018|page=7}}",
        )

    def test_translate_references_should_return_nothing(self):
        refs = ["|erroneously parsed_reference", "<references />", "[[category:"]
        for ref in refs:
            postgrest.get_mapped_template_in_database = MagicMock()
            postgrest.get_mapped_template_in_database.return_value = None
            references.translate_references([ref], "en", "mg")
