"""Translate pronunciation wikitext for publication."""

import re
from typing import Any

from .template_mapping import map_template_names


_LANGUAGE_PR_TEMPLATE_RE = re.compile(
    r"^(?P<language>[a-z][a-z0-9]*(?:-[a-z0-9]+)*)-pr$", re.IGNORECASE
)


def _malagasy_pronunciation_template(name: str) -> str | None:
    """Return the Malagasy Wiktionary name for a pronunciation template."""
    match = _LANGUAGE_PR_TEMPLATE_RE.fullmatch(name)
    if match is None:
        return None
    return f"{match.group('language').casefold()}-IPA"


def translate_pronunciation(section: Any, target: str = "mg") -> Any:
    """Map pronunciation template names supported by the target Wiktionary."""
    if target != "mg":
        return section
    if isinstance(section, str):
        return map_template_names(section, _malagasy_pronunciation_template)
    if isinstance(section, list):
        return [
            map_template_names(item, _malagasy_pronunciation_template)
            if isinstance(item, str)
            else item
            for item in section
        ]
    return section
