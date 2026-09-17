import logging
from typing import Any
from unittest.mock import MagicMock
from api.model.word import Entry
from api.servicemanager.nllb import DefinitionTranslationError
import pytest

from api.translation_v2.functions.definitions.language_model_based import (
    enrich_french_definition,
    enrich_english_definition,
    enrich_german_definition,
    remove_unknown_characters,
    remove_duplicate_definitions,
    remove_duplicate_words,
    remove_enrichment_artefacts,
    translate_using_dictionary,
    translate_using_nllb,
    translate_using_opus_mt,
    translate_individual_word_using_dictionary,
    fetch_whitelist,
    DUPLICATE_WORD_CONNECTORS,
    _strip_prefixes_case_insensitive,
    _strip_suffixes_case_insensitive,
    _strip_prefixes_with_caps,
    _remove_case_insensitive_prefix,
    _strip_pronoun_artifacts,
    _strip_izy_suffix_case_insensitive,
    remove_gotcha_translations,
    _remove_template_patterns,
    _process_by_language,
    _postprocess_translation,
    basic_english_score,
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
        "-ny is a",
        "-ny is an",
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

    def test_adjective_definition_enrichment_adds_translation_context(self) -> None:
        """Keep nominal context that helps NLLB translate adjectives."""
        assert enrich_english_definition("mpam", "clear") == "something that is clear"
        assert enrich_french_definition("mpam", "clair") == "quelque chose de clair"

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
        """Remove known gotcha translations."""
        translation = "famaritana malagasy and fa tsy misy dikany"
        processed = remove_gotcha_translations(translation)
        assert "famaritana malagasy" not in processed
        assert "fa tsy misy dikany" not in processed

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
        translate_individual_word_using_dictionary("word", language, "mg")

    def test_translate_using_dictionary(self, mocker) -> None:
        """Translate word-by-word using the dictionary."""
        mocker.patch(
            "api.translation_v2.functions.definitions.language_model_based.translate_individual_word_using_dictionary",
            side_effect=[["dika"], []],
        )
        result = translate_using_dictionary("word1 word2", "en", "mg")
        assert result == "dika word2"
        language_model_based.translate_individual_word_using_dictionary.assert_any_call(
            "word1", "en", "mg"
        )


def test_strip_prefixes_case_insensitive() -> None:
    """Strip prefixes regardless of case."""
    result = _strip_prefixes_case_insensitive("Prefix text", ["prefix"])
    assert result == "text"


def test_strip_suffixes_case_insensitive() -> None:
    """Strip suffixes regardless of case."""
    result = _strip_suffixes_case_insensitive("text Suffix", ["suffix"])
    assert result == "text"


def test_strip_prefixes_with_caps() -> None:
    """Strip prefixes with capitalization variants."""
    result = _strip_prefixes_with_caps("Test value", ["test"])
    assert result == "value"


def test_remove_case_insensitive_prefix() -> None:
    """Remove a single prefix regardless of case."""
    result = _remove_case_insensitive_prefix("Azony atao ny asa", "azony atao ny ")
    assert result == "asa"


def test_strip_pronoun_artifacts() -> None:
    """Strip pronoun artifacts in Malagasy definitions."""
    result = _strip_pronoun_artifacts("Izao no fanazavana", ["Izao"])
    assert result == "fanazavana"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("zavatra izy", "zavatra"),
        ("zavatra Izy", "zavatra"),
        ("zavatr' izy", "zavatr' izy"),
        ("zavatn' izy", "zavatn' izy"),
        ("zavatn'izy", "zavatn'izy"),
        ("izy", "izy"),
        ("izy izy", "izy"),
    ],
)
def test_strip_izy_suffix_case_insensitive(text: str, expected: str) -> None:
    """Strip ' izy' only when it is not preceded by a genitive marker."""
    assert _strip_izy_suffix_case_insensitive(text) == expected


def test_remove_template_patterns() -> None:
    """Remove template references from definitions."""
    definition = "{{lexique|test|en}} some <ref>ref</ref> content"
    result = _remove_template_patterns(definition, "en")
    assert "(test)" in result
    assert "<ref>" not in result


def test_process_by_language_long_definition() -> None:
    """Skip language processing for long definitions."""
    definition = "word " * 31
    result = _process_by_language(definition.strip(), "ana", "en")
    assert result == definition.strip()


def test_postprocess_translation_uses_dictionary(mocker) -> None:
    """Use dictionary translation for short outputs."""
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.translate_using_dictionary",
        return_value="dictionary",
    )
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.post_process_translation",
        return_value="dictionary",
    )
    result = _postprocess_translation("short", "ana", "en", "mg")
    assert result == "dictionary"


def test_translate_using_nllb_form_word() -> None:
    """Skip NLLB translation for form-of entries."""
    entry = Entry(entry="word", language="en", part_of_speech="e-ana", definitions=[], additional_data={})
    result = translate_using_nllb(
        entry=entry,
        definition_line="definition",
        source_language="en",
        target_language="mg",
    )
    assert str(result) == "definition"


def test_translate_using_nllb_translation_none(mocker) -> None:
    """Return untranslated when NLLB returns None."""
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.NllbDefinitionTranslation"
    ).return_value.get_translation.return_value = None
    entry = Entry(entry="word", language="en", part_of_speech="ana", definitions=[], additional_data={})
    result = translate_using_nllb(
        entry=entry,
        definition_line="definition",
        source_language="en",
        target_language="mg",
    )
    assert str(result) == "definition"


def test_translate_using_nllb_quality_error_returns_untranslated(mocker) -> None:
    """Continue processing when the NLLB service rejects one definition."""
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.NllbDefinitionTranslation"
    ).return_value.get_translation.side_effect = DefinitionTranslationError(
        "round-trip validation failed"
    )
    entry = Entry(entry="word", language="en", part_of_speech="ana", definitions=[], additional_data={})

    result = translate_using_nllb(
        entry=entry,
        definition_line="someone who smells badly, a stinker",
        source_language="en",
        target_language="mg",
    )

    assert isinstance(result, language_model_based.UntranslatedDefinition)
    assert str(result) == "someone who smells badly, a stinker"


def test_translate_using_nllb_preserves_translation_direction(mocker) -> None:
    """Construct the NLLB client with the requested source and target languages."""
    nllb = mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.NllbDefinitionTranslation"
    )
    nllb.return_value.get_translation.return_value = None

    translate_using_nllb(
        entry=Entry(entry="word", language="en", part_of_speech="ana", definitions=[], additional_data={}),
        definition_line="definition",
        source_language="en",
        target_language="mg",
    )

    nllb.assert_called_once_with(target_language="mg", source_language="en")


def test_translate_using_nllb_forwards_roundtrip_setting(mocker) -> None:
    """Resolve the runtime setting for each NLLB definition request."""
    nllb = mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.NllbDefinitionTranslation"
    )
    nllb.return_value.get_translation.return_value = None
    enabled = mocker.Mock(return_value=False)

    translate_using_nllb(
        entry=Entry(
            entry="word",
            language="en",
            part_of_speech="tamb",
            definitions=[],
            additional_data={},
        ),
        definition_line="definition",
        source_language="en",
        target_language="mg",
        nllb_roundtrip_validation_enabled=enabled,
    )

    enabled.assert_called_once_with()
    nllb.return_value.get_translation.assert_called_once_with(
        "definition",
        roundtrip_validation_enabled=False,
    )


def test_basic_english_score_normalizes_case_and_punctuation(mocker) -> None:
    """Score lexical words without making punctuation count as vocabulary."""
    mocker.patch(
        f"{BASE_MODULE}._basic_english_vocabulary",
        return_value=frozenset({"a", "simple", "word"}),
    )

    assert basic_english_score("A simple, unknown WORD!") == 0.75


def test_basic_english_score_loads_distributed_vocabulary() -> None:
    """Use the vocabulary file supplied in user_data."""
    assert basic_english_score("Ability able about above") == 1.0


def test_low_basic_english_score_reformulates_before_nllb(mocker) -> None:
    """Route enabled low-vocabulary English definitions through Gemma first."""
    mocker.patch(f"{BASE_MODULE}.basic_english_score", return_value=0.5)
    gemma = mocker.patch(f"{BASE_MODULE}.GemmaDefinitionReformulator")
    gemma.return_value.reformulate.return_value = "a simple description of the same thing"
    nllb = mocker.patch(f"{BASE_MODULE}.NllbDefinitionTranslation")
    nllb.return_value.get_translation.return_value = "famaritana tsotra"

    translate_using_nllb(
        entry=Entry(entry="word", language="en", part_of_speech="tamb", definitions=[], additional_data={}),
        definition_line="an abstruse and extraordinarily convoluted lexical description",
        source_language="en",
        target_language="mg",
        basic_english_gate_enabled=lambda: True,
    )

    gemma.return_value.reformulate.assert_called_once_with(
        "an abstruse and extraordinarily convoluted lexical description"
    )
    nllb.return_value.get_translation.assert_called_once_with(
        "a simple description of the same thing"
    )


def test_basic_english_gate_logs_when_running(mocker, caplog) -> None:
    """Make enabled gate evaluation visible to operators."""
    mocker.patch(f"{BASE_MODULE}.basic_english_score", return_value=0.8)

    with caplog.at_level(logging.INFO):
        language_model_based._should_reformulate_with_gemma(
            "one two three four five six seven", "en", lambda: True
        )

    assert "Basic English vocabulary gate running: score=0.800" in caplog.text


def test_basic_english_gate_logs_configuration_skip(mocker, caplog) -> None:
    """State explicitly when configuration disables an applicable gate."""
    score = mocker.patch(f"{BASE_MODULE}.basic_english_score")

    with caplog.at_level(logging.INFO):
        language_model_based._should_reformulate_with_gemma(
            "one two three four five six seven", "en", lambda: False
        )

    assert "Basic English vocabulary gate skipped per configuration" in caplog.text
    score.assert_not_called()


@pytest.mark.parametrize(
    ("definition", "source_language", "score"),
    [
        ("one two three four five six", "en", 0.0),
        ("one two three four five six seven", "en", 0.75),
        ("un deux trois quatre cinq six sept", "fr", 0.0),
    ],
)
def test_basic_english_gate_bypasses_gemma_when_not_required(
    mocker, definition: str, source_language: str, score: float
) -> None:
    """Only English definitions over six words and below 75% use Gemma."""
    mocker.patch(f"{BASE_MODULE}.basic_english_score", return_value=score)
    gemma = mocker.patch(f"{BASE_MODULE}.GemmaDefinitionReformulator")
    nllb = mocker.patch(f"{BASE_MODULE}.NllbDefinitionTranslation")
    nllb.return_value.get_translation.return_value = "teny voadika"

    translate_using_nllb(
        entry=Entry(entry="word", language=source_language, part_of_speech="tamb", definitions=[], additional_data={}),
        definition_line=definition,
        source_language=source_language,
        target_language="mg",
        basic_english_gate_enabled=lambda: True,
    )

    gemma.assert_not_called()


def test_gemma_failure_does_not_send_complex_definition_to_nllb(mocker) -> None:
    """Do not bypass an enabled gate when Gemma reformulation fails."""
    mocker.patch(f"{BASE_MODULE}.basic_english_score", return_value=0.5)
    mocker.patch(
        f"{BASE_MODULE}.GemmaDefinitionReformulator"
    ).return_value.reformulate.side_effect = RuntimeError("offline")
    nllb = mocker.patch(f"{BASE_MODULE}.NllbDefinitionTranslation")

    result = translate_using_nllb(
        entry=Entry(entry="word", language="en", part_of_speech="tamb", definitions=[], additional_data={}),
        definition_line="an abstruse and extraordinarily convoluted lexical description",
        source_language="en",
        target_language="mg",
        basic_english_gate_enabled=lambda: True,
    )

    assert isinstance(result, language_model_based.UntranslatedDefinition)
    nllb.assert_not_called()


@pytest.mark.parametrize(
    ("source_language", "definition"),
    [("en", "clear"), ("fr", "clair")],
)
def test_translate_using_nllb_strips_nominal_context_after_translation(
    mocker: Any,
    source_language: str,
    definition: str,
) -> None:
    """Use adjective context for NLLB but remove its Malagasy nominal prefix."""
    nllb = mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.NllbDefinitionTranslation"
    )
    nllb.return_value.get_translation.return_value = "zavatra ⁇ iray izay mazava"
    dictionary = mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.translate_using_dictionary",
        return_value="mazava",
    )
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.post_process_translation",
        side_effect=lambda translation: translation,
    )
    translated_definition = mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.TranslatedDefinition"
    )

    translate_using_nllb(
        entry=Entry(
            entry="word",
            language=source_language,
            part_of_speech="mpam",
            definitions=[],
            additional_data={},
        ),
        definition_line=definition,
        source_language=source_language,
        target_language="mg",
    )

    enriched_definition = {
        "en": f"something that is {definition}",
        "fr": f"quelque chose de {definition}",
    }[source_language]
    nllb.return_value.get_translation.assert_called_once_with(enriched_definition)
    dictionary.assert_called_once_with("mazava", source_language, "mg")
    translated_definition.assert_called_once_with("mazava")


def test_translate_using_nllb_translation_too_long(mocker) -> None:
    """Reject translations that are far longer than the original."""
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.NllbDefinitionTranslation"
    ).return_value.get_translation.return_value = "a " * 200
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based._postprocess_translation",
        return_value="a " * 200,
    )
    entry = Entry(entry="word", language="en", part_of_speech="ana", definitions=[], additional_data={})
    result = translate_using_nllb(
        entry=entry,
        definition_line="this is long enough",
        source_language="en",
        target_language="mg",
    )
    assert str(result) == "this is long enough"


def test_translate_using_nllb_empty_translation(mocker) -> None:
    """Return untranslated when postprocessing empties the translation."""
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.NllbDefinitionTranslation"
    ).return_value.get_translation.return_value = "content"
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based._postprocess_translation",
        return_value="",
    )
    entry = Entry(entry="word", language="en", part_of_speech="ana", definitions=[], additional_data={})
    result = translate_using_nllb(
        entry=entry,
        definition_line="definition",
        source_language="en",
        target_language="mg",
    )
    assert str(result) == "definition"


def test_translate_using_nllb_rejects_verbatim_copy(mocker) -> None:
    """Reject a translation that reproduces the enriched source text."""
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.NllbDefinitionTranslation"
    ).return_value.get_translation.return_value = "He is able to lose competition."
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based._postprocess_translation",
        return_value="He is able to lose competition.",
    )
    entry = Entry(entry="word", language="en", part_of_speech="mat", definitions=[], additional_data={})
    result = translate_using_nllb(
        entry=entry,
        definition_line="lose competition",
        source_language="en",
        target_language="mg",
    )
    assert str(result) == "lose competition"


def test_translate_using_nllb_accepts_real_translation(mocker) -> None:
    """Accept a translation that differs from the source text."""
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.NllbDefinitionTranslation"
    ).return_value.get_translation.return_value = "mahavita resy amin'ny fifaninanana"
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based._postprocess_translation",
        return_value="mahavita resy amin'ny fifaninanana",
    )
    entry = Entry(entry="word", language="en", part_of_speech="mat", definitions=[], additional_data={})
    translate_using_nllb(
        entry=entry,
        definition_line="lose competition",
        source_language="en",
        target_language="mg",
    )
    assert any(
        call.args == ("mahavita resy amin'ny fifaninanana",)
        for call in language_model_based.TranslatedDefinition.call_args_list
    )

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

    def test_remove_enrichment_artefact_only_at_the_start(self) -> None:
        """Do not remove the remnant when it is part of later source text."""
        definition = "famaritana -ny is a teny"

        assert remove_enrichment_artefacts("ana", definition) == definition

    @pytest.mark.parametrize(
        ("part_of_speech", "definition", "expected"),
        [
            ("mpam", "zavatra mazava", "mazava"),
            ("mpam", "ZAVATRA mazava", "mazava"),
            ("mpam", "zavatra izay mazava", "mazava"),
            ("mpam", "zavatra iray izay mazava", "mazava"),
            (
                "mpam",
                "zavatra iray izay zavatra iray ampiasaina",
                "zavatra iray ampiasaina",
            ),
            ("mpam", "mazava momba ny zavatra", "mazava momba ny zavatra"),
            ("ana", "zavatra mazava", "zavatra mazava"),
        ],
    )
    def test_remove_adjective_nominal_prefix(
        self,
        part_of_speech: str,
        definition: str,
        expected: str,
    ) -> None:
        """Strip generated zavatra only from the start of adjective translations."""
        assert remove_enrichment_artefacts(part_of_speech, definition) == expected

    @pytest.mark.parametrize(
        ("definition", "expected"),
        [
            ("  -NY IS A famaritana  ", "famaritana"),
            ("-ny is a", ""),
        ],
    )
    def test_remove_nllb_is_a_remnant_with_surrounding_whitespace(
        self, definition: str, expected: str
    ) -> None:
        """Strip the complete NLLB remnant after normalizing outer whitespace."""
        assert remove_enrichment_artefacts("ana", definition) == expected

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

    def test_remove_enrichment_artefacts_hoe_prefix(self) -> None:
        """Strip the 'hoe' prefix."""
        definition = "hoe zavatra"
        processed = remove_enrichment_artefacts("ana", definition)
        assert processed == "zavatra"

    def test_remove_enrichment_artefacts_noho_suffix(self) -> None:
        """Append 'izany' when suffix is 'noho'."""
        definition = "zavatra noho"
        processed = remove_enrichment_artefacts("ana", definition)
        assert processed.endswith("izany")

    def test_remove_enrichment_artefacts_izao_suffix(self) -> None:
        """Strip the 'izao' suffix."""
        definition = "zavatra izao"
        processed = remove_enrichment_artefacts("ana", definition)
        assert processed == "zavatra"

    @pytest.mark.parametrize("suffix", ["' izy", "n' izy", "n'izy"])
    def test_remove_enrichment_artefacts_keeps_izy_after_genitive(self, suffix):
        """Keep 'izy' when it follows a genitive construction ending with n'."""
        definition = f"zavatr{suffix}"
        processed = remove_enrichment_artefacts("ana", definition)
        assert processed == definition

    def test_remove_enrichment_artefacts_removes_bare_izy(self):
        """Remove 'izy' when it is a bare enrichment artifact."""
        definition = "zavatra izy"
        processed = remove_enrichment_artefacts("ana", definition)
        assert processed == "zavatra"


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


class TestRemoveDuplicateWords(LanguageModelTest):
    @pytest.mark.parametrize("connector", DUPLICATE_WORD_CONNECTORS)
    def test_remove_duplicate_words(self, connector):
        translation = f"zavatra mitohy {connector} mitohy"
        output = remove_duplicate_words(translation)
        assert (
            output == "zavatra mitohy"
        ), "Duplicate word should be removed from definition"


def test_translate_using_nltk_returns_none() -> None:
    """Return None for the NLTK translation stub."""
    result = language_model_based.translate_using_nltk(
        "ana", "definition", "en", "mg"
    )
    assert result is None


def test_translate_individual_word_without_whitelist() -> None:
    """Return empty list when language is not whitelisted."""
    result = translate_individual_word_using_dictionary("word", "xx", "mg")
    assert result == []


def test_translate_individual_word_with_whitelist(mocker) -> None:
    """Return dictionary translations when in whitelist."""
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.whitelists",
        {"xx": ["word"]},
    )
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.json_dictionary.look_up_dictionary",
        side_effect=[
            [
                {
                    "definitions": [
                        {"definition": "dika", "language": "mg"},
                        {"definition": "other", "language": "en"},
                    ]
                }
            ],
            None,
            [
                {
                    "definitions": [
                        {"definition": "dika", "language": "mg"},
                    ]
                }
            ],
            None,
            [
                {
                    "definitions": [
                        {"definition": "dika", "language": "mg"},
                    ]
                }
            ],
            None,
            [
                {
                    "definitions": [
                        {"definition": "dika", "language": "mg"},
                    ]
                }
            ],
            None,
        ],
    )
    result = translate_individual_word_using_dictionary("word", "xx", "mg")
    assert result == ["dika", "dika", "dika", "dika"]


def test_strip_prefixes_with_caps_no_match() -> None:
    """Exit after exhausting prefixes without matches."""
    result = _strip_prefixes_with_caps("value", ["missing"])
    assert result == "value"


def test_strip_pronoun_artifacts_dia() -> None:
    """Strip 'dia' artifacts and repeated pronouns."""
    result = _strip_pronoun_artifacts("Izy dia fanazavana izy", ["Izy"])
    assert result == "fanazavana"


def test_strip_pronoun_artifacts_no_prefix() -> None:
    """Strip the 'no' prefix with lowercase words."""
    result = _strip_pronoun_artifacts("izy no fanazavana izy", ["izy"])
    assert result == "fanazavana"


def test_strip_pronoun_artifacts_preserves_trailing_demonstrative() -> None:
    """Preserve demonstratives that are not repeated leading artifacts."""
    translation = (
        "fandalinana ny isam-batan'olona ao anatin'ny vondron'olona iray "
        "ao anatin'ny toe-javatra iray manokana sy ny fifandraisan'izy ireo"
    )
    result = _strip_pronoun_artifacts(translation, ["Izany", "Izao", "Izy", "Io", "Iny", "Ireo"])
    assert result == translation


def test_process_by_language_english() -> None:
    """Apply English processing for different parts of speech."""
    ana = _process_by_language("brick", "ana", "en")
    mpam = _process_by_language("clear", "mpam", "en")
    mat = _process_by_language("walk of", "mat", "en")
    assert ana.startswith("that is a ")
    assert mpam.startswith("something that is ")
    assert mat.endswith("someone or something.")


@pytest.mark.parametrize("definition", ["", "a", "b"])
def test_process_by_language_english_short_adjective_definition(definition: str) -> None:
    """Process short adjective definitions without indexing past their end."""
    assert _process_by_language(definition, "ana", "en").startswith("that is ")


def test_process_by_language_french() -> None:
    """Apply French processing for different parts of speech."""
    ana = _process_by_language("objet", "ana", "fr")
    mat = _process_by_language("aller à", "mat", "fr")
    mpam = _process_by_language("clair", "mpam", "fr")
    assert ana.startswith("cela est")
    assert "quelqu'un ou quelque chose" in mat
    assert mpam.startswith("quelque chose de ")


def test_process_by_language_german() -> None:
    """Apply German processing for different parts of speech."""
    ana = _process_by_language("wort", "ana", "de")
    mat = _process_by_language("gehen à", "mat", "de")
    assert ana.startswith("es ist ")
    assert mat.startswith("Er kannt")


def test_post_process_translation_pipeline(mocker) -> None:
    """Apply post-processing functions in order."""
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.fix_repeated_subsentence",
        return_value="step1",
    )
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.remove_empty_translations",
        return_value="step2",
    )
    mocker.patch(
        "api.translation_v2.functions.definitions.language_model_based.remove_definition_if_too_many_foreign_words",
        return_value="step3",
    )
    result = language_model_based.post_process_translation("input")
    assert result == "step3"


def test_translate_using_nllb_definition_gotcha() -> None:
    """Return untranslated when definition is a gotcha value."""
    entry = Entry(entry="word", language="en", part_of_speech="ana", definitions=[], additional_data={})
    result = translate_using_nllb(
        entry=entry,
        definition_line="famaritana malagasy",
        source_language="en",
        target_language="mg",
    )
    assert str(result) == "famaritana malagasy"
