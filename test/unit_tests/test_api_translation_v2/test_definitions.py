from copy import deepcopy
from itertools import product
from unittest import TestCase
from unittest.mock import MagicMock

from parameterized import parameterized

from api.translation_v2.exceptions import UnsupportedLanguageError
from api.translation_v2.functions.definitions import (
    database_based,
    language_model_based,
    rule_based,
)
from api.translation_v2.types import (
    UntranslatedDefinition,
    TranslatedDefinition,
    ConvergentTranslation,
)

database_based.json_dictionary = MagicMock()
entry_with_matching_definition = [
    # Simplified output (removed all timestamp details)
    {
        "type": "Word",
        "word": "semielliptic",
        "language": "en",
        "part_of_speech": "mpam",
        "definitions": [
            {
                "type": "Definition",
                "definition": "semielliptical",
                "language": "en",
            }
        ],
        "additional_data": None,
    }
]
entry_without_matching_definition = deepcopy(entry_with_matching_definition)
entry_without_matching_definition[0]["definitions"][0]["language"] = "ne"


class TestTranslateBridgeLanguageCommon(TestCase):
    def test_no_data(self):
        database_based.json_dictionary.look_up_dictionary = MagicMock()
        database_based.json_dictionary.look_up_dictionary.return_value = {}
        database_based.translate_using_bridge_language(
            part_of_speech="ana",
            definition_line="test1",
            source_language="ln",
            target_language="en",
        )
        database_based.json_dictionary.look_up_dictionary.assert_called_once()

    def test_with_data_definition_language_matches_target(self):
        database_based.json_dictionary.look_up_dictionary = MagicMock()
        database_based.json_dictionary.look_up_dictionary.return_value = (
            entry_with_matching_definition
        )
        database_based.translate_using_bridge_language(
            part_of_speech="ana",
            definition_line="test1",
            source_language="ln",
            target_language="nl",
        )
        database_based.json_dictionary.look_up_dictionary.assert_called()

    def test_with_data_definition_language_doesnt_match_target(self):
        database_based.json_dictionary.look_up_dictionary = MagicMock()
        database_based.json_dictionary.look_up_dictionary.return_value = (
            entry_without_matching_definition
        )
        database_based.translate_using_bridge_language(
            part_of_speech="ana",
            definition_line="test1",
            source_language="ln",
            target_language="nl",
        )
        database_based.json_dictionary.look_up_dictionary.assert_called()


class TestDefinitionsFormOfTemplates(TestCase):
    parameters = [
        # (
        #     "es",
        #     "{{es-verb form of|parametrar|ending=-ar|mood=subjunctive|tense=imperfect|number=p|person=3|sera=ra}}",
        # ),
        ("fr", "{{inflection of|fr|décoller||3|p|futr}}"),
        ("de", "{{past participle of|de|übersetzen}}"),
        ("lv", "{{lv-inflection of|acs ābols|loc|s}}"),
        # ('lt', '{{noun form of|lt|anyta||loc|p}}'),
    ]
    test_language = ["en", "mg"]

    @parameterized.expand(product(parameters, test_language))
    def test_translate_form_of_templates(
        self, language_and_definition, target_language
    ):
        language, definition = language_and_definition
        for pos in ["e-mat", "mat"]:
            entry = MagicMock()
            entry.part_of_speech = pos
            return_data = rule_based.FormOfDefinitionTranslatorFactory('en').translate_form_of_templates(
                entry, definition, language, target_language
            )
            self.assertIsInstance(
                return_data,
                TranslatedDefinition,
                (pos, target_language, language_and_definition, return_data.__class__),
            )


class TestUsingPostgres(TestCase):
    def test_translate_using_postgrest_json_dictionary_no_data(self):
        database_based.json_dictionary.look_up_dictionary = MagicMock()
        database_based.json_dictionary.look_up_dictionary.return_value = {}
        returned = database_based.translate_using_postgrest_json_dictionary(
            part_of_speech="ana",
            definition_line="test1",
            source_language="ln",
            target_language="nl",
        )
        self.assertIsInstance(returned, UntranslatedDefinition)

    def test_translate_using_postgrest_json_dictionary(self):
        database_based.json_dictionary.look_up_dictionary = MagicMock()
        database_based.json_dictionary.look_up_dictionary.return_value = (
            entry_with_matching_definition
        )
        returned = database_based.translate_using_postgrest_json_dictionary(
            part_of_speech="ana",
            definition_line="test1",
            source_language="ln",
            target_language="en",
        )
        self.assertIsInstance(returned, TranslatedDefinition)


class TranslateUsingConvergentDefinition(TestCase):
    translation = [
        {
            "word_id": 82617,
            "word": "cranc",
            "language": "nl",
            "part_of_speech": "ana",
            "en_definition_id": 4326382,
            "en_definition": "crab",
            "fr_definition_id": 4479658,
            "fr_definition": "crabe",
            "mg_definition_id": 9455,
            "suggested_definition": "antsavy",
        }
    ]

    def test_other_source(self):
        conv_trans_class_mock = MagicMock()
        conv_trans_class_mock.get_convergent_translation.return_value = self.translation
        database_based.ConvergentTranslations = conv_trans_class_mock

        part_of_speech = "ana"
        definition_line = "test1"
        source_language = "nk"
        target_language = "nl"

        try:
            returned = database_based.translate_using_convergent_definition(
                part_of_speech=part_of_speech,
                definition_line=definition_line,
                source_language=source_language,
                target_language=target_language,
            )
            self.assertIsInstance(returned, ConvergentTranslation)
            conv_trans_class_mock.assert_called()
        except UnsupportedLanguageError:
            pass
        else:
            raise AssertionError(
                "Did not raise expected UnsupportedLanguageError."
                " Newly supported language?"
            )

    def test_translate_using_bridge_language(self):
        database_based._translate_using_bridge_language = MagicMock()
        database_based.translate_using_bridge_language("ana", "test", "en", "mg")


class TestMachineLearningMethods(TestCase):
    def test_translate_using_nltk(self):
        language_model_based.translate_using_nltk("ana", "test", "en", "mg")

    # def test_translate_using_opus_mt(self):
    #     database_based.translate_using_opus_mt('ana', 'test', 'en', 'mg')
