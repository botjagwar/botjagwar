"""Behavioral tests for definition postprocessing and local dictionary loading."""

from pathlib import Path

import pytest

from api.translation_v2.functions.definitions import postprocessors


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("alpha beta alpha beta alpha beta tail", "alpha beta tail"),
        ("word word word word", "word"),
        ("no repeated phrase here", "no repeated phrase here"),
        ("", ""),
    ],
)
def test_fix_repeated_subsentence(sentence: str, expected: str) -> None:
    """Only phrases repeated at least three consecutive times should collapse."""
    assert postprocessors.fix_repeated_subsentence(sentence) == expected


def test_load_whitelist_normalizes_sources_and_ignores_blank_lines(tmp_path: Path) -> None:
    """Whitelist loading should retain source terms and normalize hyphenated spelling."""
    whitelist = tmp_path / "whitelist"
    whitelist.write_text("well-known -> fantatra\nplain\n\n", encoding="utf-8")

    assert postprocessors._load_whitelist(whitelist) == {"wellknown", "plain"}


def test_load_whitelist_returns_empty_set_for_missing_file(tmp_path: Path) -> None:
    """An absent optional whitelist should not prevent module use."""
    assert postprocessors._load_whitelist(tmp_path / "missing") == set()


def test_load_translation_dict_filters_invalid_and_identity_rows(tmp_path: Path) -> None:
    """Translation loading should lowercase keys and skip malformed or no-op mappings."""
    dictionary = tmp_path / "translations"
    dictionary.write_text(
        "Hello -> Miarahaba\nSame -> Same\nmalformed row\nA -> target -> suffix\n",
        encoding="utf-8",
    )

    assert postprocessors._load_translation_dict(dictionary) == {
        "hello": "Miarahaba",
        "a": "target -> suffix",
    }


def test_load_translation_dict_returns_empty_dict_for_missing_file(tmp_path: Path) -> None:
    """An absent optional translation dictionary should yield no mappings."""
    assert postprocessors._load_translation_dict(tmp_path / "missing") == {}


@pytest.mark.parametrize(
    ("definition", "expected"),
    [("ny", None), ("hoe", None), ("ny teny", "ny teny"), ("", "")],
)
def test_remove_empty_translations(definition: str, expected: str | None) -> None:
    """Only known empty machine-translation placeholders should be discarded."""
    assert postprocessors.remove_empty_translations(definition) == expected


def test_foreign_word_filter_handles_empty_definition() -> None:
    """Empty definitions should be rejected before configuration or token processing."""
    assert postprocessors.remove_definition_if_too_many_foreign_words("") is None


def test_foreign_word_filter_respects_normalized_tokens_and_threshold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Known Malagasy tokens should not consume the configured foreign-word allowance."""
    config = tmp_path / "config.ini"
    config.write_text("[nllb]\nremaining_words_threshold = 1\n", encoding="utf-8")
    monkeypatch.setattr(postprocessors, "CONFIG_PATH", config)
    monkeypatch.setattr(postprocessors, "TRANSLATION_DICT_mg", {"known", "word"})

    assert postprocessors.remove_definition_if_too_many_foreign_words("Known-word unknown") == "Known-word unknown"
    assert postprocessors.remove_definition_if_too_many_foreign_words("known first second") is None


def test_foreign_word_filter_uses_zero_fallback_when_config_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without an nllb setting, only definitions entirely in the local dictionary pass."""
    monkeypatch.setattr(postprocessors, "CONFIG_PATH", tmp_path / "missing.ini")
    monkeypatch.setattr(postprocessors, "TRANSLATION_DICT_mg", {"teny", "fantatra"})

    assert postprocessors.remove_definition_if_too_many_foreign_words("teny fantatra") == "teny fantatra"
    assert postprocessors.remove_definition_if_too_many_foreign_words("teny foreign") is None


def test_foreign_word_filter_rejects_majority_foreign_definition(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Definitions mostly made of foreign words are untranslated and rejected."""
    config = tmp_path / "config.ini"
    config.write_text("[nllb]\nremaining_words_threshold = 4\n", encoding="utf-8")
    monkeypatch.setattr(postprocessors, "CONFIG_PATH", config)
    monkeypatch.setattr(
        postprocessors,
        "TRANSLATION_DICT_mg",
        {"he", "to", "mahavita", "resy", "amin", "ny", "fifaninanana"},
    )

    assert postprocessors.remove_definition_if_too_many_foreign_words(
        "he is able to lose competition"
    ) is None
    assert postprocessors.remove_definition_if_too_many_foreign_words(
        "mahavita resy amin'ny fifaninanana"
    ) == "mahavita resy amin'ny fifaninanana"
