"""Shared quality checks for machine translations."""

from __future__ import annotations

import re
from difflib import SequenceMatcher


DEFAULT_ROUNDTRIP_LEXICAL_SIMILARITY_THRESHOLD = 0.35
DEFAULT_ROUNDTRIP_TOKEN_OVERLAP_THRESHOLD = 0.25
DEFAULT_ROUNDTRIP_LENGTH_RATIO_LIMIT = 2.0


def get_roundtrip_validation_error(
    original_text: str,
    roundtrip_text: str,
    semantic_similarity: float,
    *,
    semantic_threshold: float,
    lexical_threshold: float = DEFAULT_ROUNDTRIP_LEXICAL_SIMILARITY_THRESHOLD,
) -> str | None:
    """Return why a back-translation is not faithful, or ``None`` if it is."""
    original_tokens = _tokens(original_text)
    roundtrip_tokens = _tokens(roundtrip_text)
    if not original_tokens or not roundtrip_tokens:
        return "the original or round-trip text has no comparable terms"

    original_numbers = [token for token in original_tokens if token.isdigit()]
    roundtrip_numbers = [token for token in roundtrip_tokens if token.isdigit()]
    if original_numbers != roundtrip_numbers:
        return "numbers changed during the round trip"

    length_ratio = len(roundtrip_tokens) / len(original_tokens)
    ratio_limit = DEFAULT_ROUNDTRIP_LENGTH_RATIO_LIMIT
    if not 1 / ratio_limit <= length_ratio <= ratio_limit:
        return f"token length ratio {length_ratio:.3f} is outside the allowed range"

    original_normalised = " ".join(original_tokens)
    roundtrip_normalised = " ".join(roundtrip_tokens)
    lexical_similarity = SequenceMatcher(
        None,
        original_normalised,
        roundtrip_normalised,
        autojunk=False,
    ).ratio()
    original_token_set = set(original_tokens)
    roundtrip_token_set = set(roundtrip_tokens)
    token_overlap = len(original_token_set & roundtrip_token_set) / len(
        original_token_set | roundtrip_token_set
    )
    if len(original_tokens) >= 4 and (
        lexical_similarity < lexical_threshold
        or token_overlap < DEFAULT_ROUNDTRIP_TOKEN_OVERLAP_THRESHOLD
    ):
        return (
            "lexical similarity is too low "
            f"(sequence={lexical_similarity:.3f}, token_overlap={token_overlap:.3f})"
        )

    if semantic_similarity < semantic_threshold:
        return (
            f"cosine similarity {semantic_similarity:.3f} is below threshold "
            f"{semantic_threshold:.3f}"
        )
    return None


def _tokens(text: str) -> list[str]:
    """Return case-insensitive word and number tokens for comparison."""
    return re.findall(r"\b[\w'-]+\b", text.casefold())
