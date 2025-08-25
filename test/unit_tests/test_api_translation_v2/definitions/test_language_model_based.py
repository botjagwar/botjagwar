from unittest.mock import MagicMock
from api.model.word import Entry
import pytest

from api.translation_v2.functions.definitions.language_model_based import (
    enrich_french_definition,
    enrich_english_definition,
    enrich_german_definition,
    remove_unknown_characters,
    remove_duplicate_definitions,
    remove_enrichment_artefacts,
    translate_using_dictionary,
    translate_using_nllb,
    translate_using_opus_mt,
    translate_individual_word_using_dictionary,
    fetch_whitelist,
)

# monkey patch all imports by api.translation_v2.functions.definitions.language_model_based
import api.translation_v2.functions.definitions.language_model_based as language_model_based

language_model_based.json_dictionary = MagicMock()
language_model_based.NllbDefinitionTranslation = MagicMock()
language_model_based.OpenMtTranslation = MagicMock()
language_model_based.JsonDictionary = MagicMock()
language_model_based.TranslatedDefinition = MagicMock()
language_model_based.ConvergentTranslations = MagicMock()

BASE_MODULE = "api.translation_v2.functions.definitions.language_model_based"


@pytest.fixture(scope="function", name="nllb_definition_translation")
def nllb_definition_translation_fixture(mocker):
    return mocker.patch(f"{BASE_MODULE}.NllbDefinitionTranslation")


@pytest.fixture(scope="function", name="openmttranslation")
def openmttranslation_fixture(mocker):
    return mocker.patch(f"{BASE_MODULE}.OpenMtTranslation")


@pytest.fixture(scope="function", name="jsondictionary")
def jsondictionary_fixture(mocker):
    return mocker.patch(f"{BASE_MODULE}.JsonDictionary")


@pytest.fixture(scope="function", name="convergenttranslations")
def convergenttranslations_fixture(mocker):
    return mocker.patch(f"{BASE_MODULE}.ConvergentTranslations")


class LanguageModelTest:
    ENTRIES = [
        Entry(entry='Entry1', language="de", part_of_speech="ana", definitions=["definition1", "definition2"], additional_data={}),
        Entry(entry='Entry2', language="fr", part_of_speech="mat", definitions=["definition3"], additional_data={}),
        Entry(entry='Entṙy3', language="en", part_of_speech="mpam", definitions=["definition4"], additional_data={}),
        Entry(entry='ėntry4', language="es", part_of_speech="tamb", definitions=["definition5"], additional_data={}),
        Entry(entry='éntry5', language="ko", part_of_speech="tovona", definitions=["definition6"], additional_data={}),
        Entry(entry='ẽntry6', language="vi", part_of_speech="tovana", definitions=["definition7"], additional_data={}),
        Entry(entry='Entry7', language="id", part_of_speech="e-ana", definitions=["definition8"], additional_data={}),
        Entry(entry='Entry8', language="ms", part_of_speech="e-mat", definitions=["definition9"], additional_data={}),
        Entry(entry='Entry9', language="tr", part_of_speech="e-mpam", definitions=["definition10"], additional_data={}),
    ]
    PARTS_OF_SPEECH = [
        "ana",
        "mat",
        "mpam",
        "tamb",
        "tovona",
        "tovana",
        "e-ana",
        "e-mat",
        "e-mpam",
    ]
    WORDS = ["føsk", "mést", "ðadidu", "óqlla"]
    JOINERS = ["sady", "sy"]

    STARTSWITH = [
        "afaka",
        "izay",
        "fa",
        "mahay",
        "mahavita",
        "dia",
        "azo atao ny",
        "azony atao ny",
        "no",
        "cela dia",
        "Ny cela dia",
    ]
    ENDSWITH = ["ho azy", "azy", "izy", "izany", "izao"]


class TestLanguageModelBased(LanguageModelTest):
    """Unit tests for LanguageModelBased."""

    @pytest.mark.parametrize("returned_data", [None, "some-data"])
    def test_translate_using_opus_mt(self, returned_data, openmttranslation):
        openmttranslation.return_value.get_translation.return_value = returned_data
        translate_using_opus_mt(
            part_of_speech="ana",
            definition_line="definition",
            source_language="en",
            target_language="mg",
        )
        openmttranslation.return_value.get_translation.assert_called_once()

    @pytest.mark.parametrize("part_of_speech", LanguageModelTest.PARTS_OF_SPEECH)
    @pytest.mark.parametrize("postposition", ["", "to", "of"])
    @pytest.mark.parametrize("preposition", ["", "of", "to", "a", "an"])
    def test_enrich_english_definition(self, part_of_speech, preposition, postposition):
        text = f"{preposition} definition {postposition}".strip()
        enriched = enrich_english_definition(part_of_speech, text)
        assert text in enriched, "Definition should be found in enriched definition"

    @pytest.mark.parametrize("preposition", ["", "un", "une"])
    @pytest.mark.parametrize("postposition", ["", "à"])
    @pytest.mark.parametrize("part_of_speech", LanguageModelTest.PARTS_OF_SPEECH)
    def test_enrich_french_definition(self, part_of_speech, preposition, postposition):
        text = f"{preposition} définition {postposition}".strip()
        enriched = enrich_french_definition(part_of_speech, text)

        assert text in enriched, "Definition should be found in enriched definition"

    @pytest.mark.parametrize("part_of_speech", LanguageModelTest.PARTS_OF_SPEECH)
    def test_enrich_german_definition(self, part_of_speech):
        enriched = enrich_german_definition(part_of_speech, "Definizion")

        assert (
            "Definizion" in enriched
        ), "Definition should be found in enriched definition"

    @pytest.mark.parametrize("translation", ["⁇translated⁇", "translated"])
    def test_remove_unknown_characters(self, translation):
        output = remove_unknown_characters(translation)
        assert "⁇" not in output, "Unknown characters should be removed"

    def test_remove_gotcha_translations(self):
        pass

    @pytest.mark.parametrize("language", ["en", "fr"])
    @pytest.mark.parametrize("part_of_speech", ["ana", "mat", "mpam", "tamb"])
    def test_translate_individual_word_using_dictionary(self, language, part_of_speech):
        language_model_based.json_dictionary.return_value.look_up_dictionary.return_value = [
            {
                "language": language,
                "part_of_speech": part_of_speech,
                "word": "word",
                "definitions": {
                    "definition": "definition",
                    "definition_language": "mg",
                },
            }
        ]
        fetch_whitelist("en")
        translation = translate_individual_word_using_dictionary("word", language, "mg")

    def test_translate_using_dictionary(self):
        pass

    @pytest.mark.parametrize("language", ["en", "fr", "de"])
    @pytest.mark.parametrize("entry", LanguageModelTest.ENTRIES)
    def test_translate_using_nllb(
        self,
        language,
        entry,
        nllb_definition_translation,
        openmttranslation,
        jsondictionary,
        convergenttranslations,
    ):
        nllb_definition_translation.return_value.get_translation.return_value = (
            "afaka manao fandikana tena mendrika"
        )

        translate_using_nllb(
            entry=entry,
            source_language=language,
            target_language="mg",
            definition_line="a very good definition",
        )

    @pytest.mark.parametrize("gotcha", ["famaritana malagasy", "fa tsy misy dikany"])
    def test_translate_using_nllb_gotchas(
        self,
        gotcha,
        nllb_definition_translation,
        openmttranslation,
        jsondictionary,
        convergenttranslations,
    ):
        nllb_definition_translation.return_value.get_translation.return_value = gotcha

        translate_using_nllb(
            entry=Entry(entry="word", language="mg", part_of_speech="ana", definitions=[], additional_data={}),
            source_language="en",
            target_language="mg",
            definition_line="a very good definition",
        )


class TestRemoveEnrichmentArtefacts(LanguageModelTest):
    @pytest.mark.parametrize("parametered_definition", ["definition", "famaritana"])
    @pytest.mark.parametrize("startswith", LanguageModelTest.STARTSWITH)
    def test_remove_enrichment_artefacts_startswith(
        self, parametered_definition, startswith
    ):
        definition = f"{startswith} {parametered_definition}"
        processed = remove_enrichment_artefacts("ana", definition)
        assert (
            parametered_definition in processed
        ), "Definition should be found in processed definition"
        assert (
            f"{startswith} " not in processed
        ), "Enrichment artefact should be removed from processed definition"

    @pytest.mark.parametrize("preposition", ["a", "an"])
    def test_remove_enrichment_artefacts_preposition(self, preposition):
        definition = f"{preposition} definition"
        processed = remove_enrichment_artefacts("ana", definition)
        assert (
            "definition" in processed
        ), "Definition should be found in processed definition"
        assert (
            preposition not in processed
        ), "Enrichment artefact should be removed from processed definition"

    @pytest.mark.parametrize("startswith", "Izany Izao Izy Io Iny Ireo".split())
    def test_remove_enrichment_artefacts_startswith_set_2(self, startswith):
        for w in [" ", " no ", " dia "]:
            definition = f"{startswith}{w}definition"
            processed = remove_enrichment_artefacts("ana", definition)
            assert (
                "definition" in processed
            ), "Definition should be found in processed definition"
            assert (
                startswith not in processed
            ), "Enrichment artefact should be removed from processed definition"

    @pytest.mark.parametrize("endswith", LanguageModelTest.ENDSWITH)
    def test_remove_enrichment_artefacts_endswith(self, endswith):
        definition = f"definition {endswith}"
        processed = remove_enrichment_artefacts("ana", definition)
        assert (
            "definition" in processed
        ), "Definition should be found in processed definition"
        assert (
            endswith not in processed
        ), "Enrichment artefact should be removed from processed definition"

    @pytest.mark.parametrize("startswith", LanguageModelTest.STARTSWITH)
    @pytest.mark.parametrize("part_of_speech", ["ana", "mat"])
    def test_remove_enrichment_artefacts_part_of_speech_startswith(
        self, startswith, part_of_speech
    ):
        definition = f"{startswith} definition"
        processed = remove_enrichment_artefacts(part_of_speech, definition)
        assert (
            "definition" in processed
        ), "Definition should be found in processed definition"
        assert (
            startswith not in processed
        ), "Enrichment artefact should be removed from processed definition"

    @pytest.mark.parametrize("endswith", LanguageModelTest.ENDSWITH)
    @pytest.mark.parametrize("part_of_speech", ["ana", "mat"])
    def test_remove_enrichment_artefacts_part_of_speech_endswith(
        self, endswith, part_of_speech
    ):
        definition = f"definition {endswith}"
        processed = remove_enrichment_artefacts(part_of_speech, definition)
        assert (
            "definition" in processed
        ), "Definition should be found in processed definition"
        assert (
            endswith not in processed
        ), "Enrichment artefact should be removed from processed definition"


class TestRemoveDuplicateDefinitions(LanguageModelTest):
    @pytest.mark.parametrize("joiner", ["; ", ", ", " sy ", " na "])
    @pytest.mark.parametrize("word", LanguageModelTest.WORDS)
    def test_remove_duplicate_definitions_with_punctuation_same_case(
        self, word, joiner
    ):
        word1 = word
        word2 = word
        translation = f"{word1}{joiner}{word2}"
        output = remove_duplicate_definitions(translation)
        assert output.count(word) == 1, "same word found more than once."

    @pytest.mark.parametrize("joiner", [";", ","])
    @pytest.mark.parametrize("word", LanguageModelTest.WORDS)
    def test_remove_duplicate_definitions_with_punctuation_title_and_lowercase(
        self, word, joiner
    ):
        word1 = word.title()
        word2 = word.lower()
        translation = f"{word1}{joiner} {word2}"
        output = remove_duplicate_definitions(translation)
        assert word1 in output, "First word should be found in output"

    @pytest.mark.parametrize("joiner", [" sy ", " na "])
    @pytest.mark.parametrize("word", LanguageModelTest.WORDS)
    def test_remove_duplicate_definitions_with_conjunctions(self, word, joiner):
        word1 = word.title()
        word2 = word.lower()
        translation = f"{word1}{joiner}{word2}"
        output = remove_duplicate_definitions(translation)
        assert word1 in output, "First word should be found in output"
        assert word2 not in output, "Second word should be removed from output"
