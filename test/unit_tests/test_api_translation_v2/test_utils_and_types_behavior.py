"""Offline behavioral tests for translation utilities and value types."""

from types import SimpleNamespace
from unittest.mock import MagicMock, call

from api.translation_v2.functions import utils
from api.translation_v2.types import (
    ConvergentTranslation,
    FormOfTranslaton,
    TranslatedDefinition,
    UntranslatedDefinition,
)


class AnnotatedText(str):
    """String carrying metadata used to verify attribute delegation."""

    source = "dictionary"


def test_delink_prefers_link_target_and_removes_remaining_markup() -> None:
    """Wiki links should become plain target text and all bracket markup should disappear."""
    assert utils._delink("[[target|Label]] {{tag}} [plain]") == "target tag plain"


def test_delink_removes_wiktionary_section_fragments() -> None:
    """Section fragments and pipes must not leak into dictionary lookup text."""
    definition = "to (politely) [[request#English|request]] something"

    assert utils._delink(definition) == "to (politely) request something"
    assert utils._delink("[[#English|request]]") == "request"


def test_generate_redirections_normalizes_cyrillic_entries_in_place() -> None:
    """Cyrillic-language redirects should remove accents and use the Cyrillic ae glyph."""
    infos = SimpleNamespace(entry="ḿæ̀", language="ru")

    utils._generate_redirections(infos)

    assert infos.entry == "mӕ"


def test_generate_redirections_leaves_other_languages_unchanged() -> None:
    """Normalization rules specific to Cyrillic languages must not affect Latin entries."""
    infos = SimpleNamespace(entry="ḿæ", language="en")

    assert utils._generate_redirections(infos) is None
    assert infos.entry == "ḿæ"


def test_generate_redirections_does_not_reassign_an_already_normalized_entry() -> None:
    """A normalized Cyrillic entry should remain stable."""
    infos = SimpleNamespace(entry="слово", language="uk")

    utils._generate_redirections(infos)

    assert infos.entry == "слово"


def test_filter_additional_data_preserves_identity() -> None:
    """The pass-through filter should return the caller-owned mapping itself."""
    additional_data = {"reference": ["source"]}

    assert utils.filter_additional_data(additional_data) is additional_data


def test_try_methods_stops_at_first_translated_definition_and_forwards_arguments() -> None:
    """Translation strategy fallback should short-circuit only on the marker result type."""
    untranslated = MagicMock(return_value=UntranslatedDefinition("source"))
    untranslated.__name__ = "untranslated"
    successful_result = TranslatedDefinition("translated")
    successful_result.languages = ["en"]
    successful = MagicMock(return_value=successful_result)
    successful.__name__ = "successful"
    skipped = MagicMock(return_value=TranslatedDefinition("not reached"))
    skipped.__name__ = "skipped"
    translate = utils.try_methods_until_translated(untranslated, successful, skipped)

    result = translate("definition", target_language="mg")

    assert result is successful_result
    untranslated.assert_called_once_with("definition", target_language="mg")
    successful.assert_called_once_with("definition", target_language="mg")
    skipped.assert_not_called()
    assert translate.__name__ == "successful"


def test_try_methods_returns_none_after_all_nontranslated_results() -> None:
    """Exhausted strategies should return None rather than an untranslated intermediate value."""
    first = MagicMock(return_value="plain string")
    first.__name__ = "first"
    second = MagicMock(return_value=None)
    second.__name__ = "second"

    result = utils.try_methods_until_translated(first, second)("definition")

    assert result is None
    assert first.call_args_list == [call("definition")]
    assert second.call_args_list == [call("definition")]


def test_untranslated_definition_repr_identifies_its_marker_type() -> None:
    """The untranslated marker should have a diagnostic representation."""
    definition = UntranslatedDefinition("source text")

    assert str(definition) == "source text"
    assert repr(definition) == "UntranslatedDefinition(source text)"


def test_translated_definition_exposes_translation_behavior_and_languages() -> None:
    """Translated values should concatenate, stringify, and delegate translation metadata."""
    translation = AnnotatedText("target text")
    definition = TranslatedDefinition(translation)
    definition.languages = ["en", "fr"]

    assert str(definition) == "target text"
    assert definition + " suffix" == "target text suffix"
    assert definition + 3 is None
    assert definition.source == "dictionary"
    assert definition.missing_attribute is None
    assert definition.languages == ["en", "fr"]


def test_translated_definition_defaults_languages_per_instance_and_formats_repr() -> None:
    """Default language lists should be independent and repr should include optional synonym data."""
    first = TranslatedDefinition("first")
    second = TranslatedDefinition("second")
    first.languages.append("en")

    assert second.languages == []
    assert repr(first) == "TranslatedDefinition(first, )"
    first.synonym = "primary"
    assert repr(first) == "TranslatedDefinition(first, primary)"


def test_convergent_translation_requires_multiple_languages() -> None:
    """A convergent result is translated only when multiple source languages agree."""
    single_source = ConvergentTranslation("target")
    single_source.languages = ["en"]
    multiple_sources = ConvergentTranslation("target")
    multiple_sources.languages = ["en", "fr"]

    assert not single_source.is_translated_definition
    assert multiple_sources.is_translated_definition


def test_form_of_translation_tracks_lemma_validity_and_metadata() -> None:
    """Form-of values should initialize metadata and reject only an explicitly empty lemma."""
    definition = FormOfTranslaton("form")
    definition.languages = ["en"]

    assert definition.part_of_speech is None
    assert definition.lemma is None
    assert definition.is_valid()
    definition.lemma = ""
    assert not definition.is_valid()
    definition.lemma = "lemma"
    definition.part_of_speech = "mat"
    assert definition.is_valid()
    assert definition.part_of_speech == "mat"
