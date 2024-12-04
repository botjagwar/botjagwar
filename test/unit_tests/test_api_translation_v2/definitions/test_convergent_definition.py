from unittest import TestCase, mock

from api.translation_v2.exceptions import UnsupportedLanguageError
from api.translation_v2.functions import translate_using_convergent_definition
from api.translation_v2.types import ConvergentTranslation


class TestTranslateUsingConvergentDefinition(TestCase):
    @mock.patch(
        "api.translation_v2.functions.definitions.database_based.convergent_translations"
    )
    def test_translate_using_convergent_definition_1(self, convergent_translations):
        # Test case 1: Successful translation from English to Spanish
        convergent_translations.get_convergent_translation.return_value = [
            {"suggested_definition": "translation 1"}
        ]
        result = translate_using_convergent_definition(
            part_of_speech="ana",
            definition_line="test definition",
            source_language="en",
            target_language="mg",
        )
        convergent_translations.get_convergent_translation.assert_called_once()

    @mock.patch(
        "api.translation_v2.functions.definitions.database_based.convergent_translations"
    )
    def test_translate_using_convergent_definition_2(self, convergent_translations):
        # Test case 2: Successful translation from French to Portuguese
        convergent_translations.get_convergent_translation.return_value = [
            {"suggested_definition": "translation 2"}
        ]
        result = translate_using_convergent_definition(
            part_of_speech="mat",
            definition_line="test definition2",
            source_language="fr",
            target_language="mg",
        )
        convergent_translations.get_convergent_translation.assert_called_once()
        self.assertEqual(result, "translation 2")
        self.assertIsInstance(result, ConvergentTranslation)

    @mock.patch("api.translation_v2.functions.definitions.convergent_translations")
    def test_translate_using_convergent_definition_3(
        self, mock_get_convergent_translation
    ):
        # Test case 3: Unsupported source language
        with self.assertRaises(UnsupportedLanguageError):
            translate_using_convergent_definition("mat", "test definition", "de", "es")
