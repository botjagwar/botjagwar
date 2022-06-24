from unittest import TestCase
from unittest.mock import MagicMock

from api.translation_v2.functions import references

references.TemplateTranslation = MagicMock()
postgrest = MagicMock()
references.TemplateTranslation.return_value = postgrest


class TestReferencesTranslator(TestCase):
    def test_translate_R_is_mapped(self):
        ref = '{{R:Translated|toto titi tata}}'
        postgrest.get_mapped_template_in_database = MagicMock()
        postgrest.get_mapped_template_in_database.return_value = None
        references.translate_reference_templates(ref, 'en', 'mg')

    def test_translate_references_is_mapped(self):
        ref = '{{R:Translated|toto titi tata}}'
        postgrest.get_mapped_template_in_database = MagicMock()
        postgrest.get_mapped_template_in_database.return_value = 'Tsiahy:Voadika'
        references.translate_references([ref], 'en', 'mg')

    def test_translate_references_is_not_mapped(self):
        ref = '{{cite-web|toto titi tata}}'
        postgrest.get_mapped_template_in_database = MagicMock()
        postgrest.get_mapped_template_in_database.return_value = None
        references.translate_references([ref], 'en', 'mg')

    def test_translate_references_should_return_nothing(self):
        refs = ['|erroneously parsed_reference', '<references />', '[[category:']
        for ref in refs:
            postgrest.get_mapped_template_in_database = MagicMock()
            postgrest.get_mapped_template_in_database.return_value = None
            references.translate_references([ref], 'en', 'mg')
