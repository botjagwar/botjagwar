"""Tests for pronunciation and template-name mapping."""

from api.translation_v2.functions.pronunciation import translate_pronunciation
from api.translation_v2.functions.template_mapping import map_template_names


def test_template_mapper_renames_nested_templates_without_changing_parameters() -> None:
    """Apply caller-defined mappings throughout a wikitext fragment."""
    mappings = {"outer": "mapped-outer", "inner": "mapped-inner"}

    mapped = map_template_names(
        "{{outer|value={{inner|name=value}}}}", mappings.get
    )

    assert mapped == "{{mapped-outer|value={{mapped-inner|name=value}}}}"


def test_pronunciation_maps_language_pr_template_for_malagasy() -> None:
    """Use the Malagasy IPA template name while preserving parameters."""
    assert translate_pronunciation("{{fr-pr|gens|a=Paris}}") == (
        "{{fr-IPA|gens|a=Paris}}"
    )


def test_pronunciation_maps_string_lists_and_preserves_other_templates() -> None:
    """Translate every pronunciation fragment without broad suffix replacement."""
    assert translate_pronunciation(
        ["{{en-pr}}", "{{roa-nor-pr|word}}", "{{zh-pron|m=word}}", 3]
    ) == ["{{en-IPA}}", "{{roa-nor-IPA|word}}", "{{zh-pron|m=word}}", 3]


def test_pronunciation_mapping_only_applies_to_malagasy_target() -> None:
    """Do not impose Malagasy template conventions on another target wiki."""
    assert translate_pronunciation("{{fr-pr|gens}}", target="en") == (
        "{{fr-pr|gens}}"
    )


def test_pronunciation_preserves_unsupported_value_shapes() -> None:
    """Retain legacy structured pronunciation values unchanged."""
    pronunciation = {"IPA": "/word/"}

    assert translate_pronunciation(pronunciation) is pronunciation
