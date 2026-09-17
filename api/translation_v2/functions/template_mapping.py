"""Reusable wikitext template-name mapping."""

from collections.abc import Callable

import mwparserfromhell


TemplateNameMapper = Callable[[str], str | None]


def map_template_names(wikitext: str, mapper: TemplateNameMapper) -> str:
    """Map template names in wikitext while preserving their parameters."""
    wikicode = mwparserfromhell.parse(wikitext)
    for template in wikicode.filter_templates(recursive=True):
        raw_name = str(template.name)
        name = raw_name.strip()
        mapped_name = mapper(name)
        if mapped_name is None or mapped_name == name:
            continue
        leading_whitespace = raw_name[: len(raw_name) - len(raw_name.lstrip())]
        trailing_whitespace = raw_name[len(raw_name.rstrip()) :]
        template.name = f"{leading_whitespace}{mapped_name}{trailing_whitespace}"
    return str(wikicode)
