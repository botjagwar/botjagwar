"""Tests for shared machine-translation quality checks."""

import pytest

from api.utils.translation_quality import get_roundtrip_validation_error


def test_accepts_faithful_roundtrip() -> None:
    """Allow a close paraphrase with strong semantic similarity."""
    assert (
        get_roundtrip_validation_error(
            "A domesticated carnivorous mammal",
            "A domestic carnivorous mammal",
            0.91,
            semantic_threshold=0.60,
        )
        is None
    )


def test_accepts_semantically_similar_short_roundtrip() -> None:
    """Do not require exact token overlap for short synonymous phrases."""
    assert (
        get_roundtrip_validation_error(
            "A peasant",
            "A farmer",
            0.88,
            semantic_threshold=0.60,
        )
        is None
    )


def test_accepts_long_faithful_roundtrip_without_autojunk() -> None:
    """Do not let SequenceMatcher's repetition heuristic reject long paraphrases."""
    assert (
        get_roundtrip_validation_error(
            "a system in which products can be labelled as sustainable or as fairtrade "
            "regardless of the background of the materials used to make the product, as "
            "long as the manufacturer has paid for an equivalent quantity of sustainable "
            "or fairtrade materials to enter the supply chain",
            "a system whereby a product can be labelled as sustainable or as fair trade "
            "regardless of the origin of the materials used to manufacture the product, "
            "if the manufacturer has paid for similar sustainable or fair trade materials "
            "to enter the supply chain",
            0.90,
            semantic_threshold=0.60,
        )
        is None
    )


@pytest.mark.parametrize(
    ("original", "roundtrip", "similarity", "reason"),
    [
        ("A vehicle used for travel", "A vehicle used for travel", 0.59, "cosine similarity"),
        ("A vehicle used for travel", "Completely unrelated output", 0.95, "lexical similarity"),
        ("that is a ox, bull", "It's a cow, a cow", 0.95, "lexical similarity"),
        (
            "that is pickle, or any pickled vegetable",
            "It's a lemon, or a lemon vegetable.",
            0.95,
            "lexical similarity",
        ),
        ("that is fine (punishment)", "that's good (punishment)", 0.95, "lexical similarity"),
        (
            "that is a thread-waisted wasp (), especially mud dauber",
            "It's a bird flag (), specifically the bird flag",
            0.95,
            "lexical similarity",
        ),
        ("Built in 1998", "Built in 1999", 0.95, "numbers changed"),
        ("A vehicle used for travel", "word " * 20, 0.95, "token length ratio"),
    ],
)
def test_rejects_roundtrip_translation_errors(
    original: str,
    roundtrip: str,
    similarity: float,
    reason: str,
) -> None:
    """Reject semantic, lexical, numeric, and length corruption."""
    error = get_roundtrip_validation_error(
        original,
        roundtrip,
        similarity,
        semantic_threshold=0.60,
    )
    assert error is not None
    assert reason in error
