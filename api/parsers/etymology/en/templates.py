from __future__ import annotations

"""Parsers for English etymology templates."""

from typing import Callable, Dict

import mwparserfromhell


def _italic(text: str) -> str:
    """Return ``text`` wrapped in italic wiki markup."""
    return f"''{text}''" if text else ""


def _lang_template(code: str) -> str:
    """Return the wiki template for a language ``code``."""
    return f"{{{{{code}}}}}" if code else ""


def parse_affix(template: mwparserfromhell.nodes.Template) -> str:
    """Render the ``af`` (affix) template to plain text."""
    lang_code = str(template.get(1).value).strip() if template.has(1) else ""
    lang_part = _lang_template(lang_code)
    parts: list[str] = []
    term_index = 1
    param_index = 2
    while template.has(param_index):
        term = str(template.get(param_index).value).strip()
        if term:
            translation_param = f"t{term_index}"
            translation = (
                str(template.get(translation_param).value).strip()
                if template.has(translation_param)
                else ""
            )
            is_affix = term.startswith("-") or term.endswith("-")
            term_text = term if is_affix else _italic(term)
            if translation:
                gloss = mwparserfromhell.parse(translation).strip_code()
                term_text += f" ({_italic(gloss)})"
            parts.append(term_text)
        term_index += 1
        param_index += 1
    joined = " + ".join(parts)
    return f"{lang_part} {joined}".strip()


def _parse_inh_der_bor(template: mwparserfromhell.nodes.Template) -> str:
    """Render inheritance/derivation/borrowing templates without relations."""
    origin_code = str(template.get(2).value).strip() if template.has(2) else ""
    term = ""
    if template.has(4) and str(template.get(4).value).strip():
        term = str(template.get(4).value).strip()
    elif template.has(3):
        term = str(template.get(3).value).strip()
    translation = str(template.get(5).value).strip() if template.has(5) else ""

    result = f"{_lang_template(origin_code)}".strip()
    if term:
        lemma_raw = term
        lemma = mwparserfromhell.parse(lemma_raw).strip_code()
        if lemma_raw.startswith("*") and not lemma.startswith("*"):
            lemma = "*" + lemma
        result += f" {_italic(lemma)}"
    if translation:
        gloss = mwparserfromhell.parse(translation).strip_code()
        result += f" ({_italic(gloss)})"
    return result.strip()


def parse_cognate(template: mwparserfromhell.nodes.Template) -> str:
    """Render the ``cog`` template to plain text."""
    lang_code = str(template.get(1).value).strip() if template.has(1) else ""
    term = str(template.get(2).value).strip() if template.has(2) else ""
    translation = ""
    if template.has(4):
        translation = str(template.get(4).value).strip()
    elif template.has(3):
        translation = str(template.get(3).value).strip()

    result = f"{_lang_template(lang_code)} {_italic(mwparserfromhell.parse(term).strip_code())}".strip()
    translation = mwparserfromhell.parse(translation).strip_code()
    if translation:
        result += f" ({_italic(translation)})"
    return result.strip()


def parse_noncognate(template: mwparserfromhell.nodes.Template) -> str:
    """Render the ``ncog`` template to plain text with a leading note."""
    rendered = parse_cognate(template)
    return f"not cognate with {rendered}" if rendered else ""


def _parse_with_prefix(
    template: mwparserfromhell.nodes.Template, prefix: str
) -> str:
    """Return parsed borrowing-like template preceded by ``prefix``."""
    rendered = _parse_inh_der_bor(template)
    return f"{prefix} {rendered}".strip() if rendered else ""


def _parse_misc_single_term(
    template: mwparserfromhell.nodes.Template, prefix: str
) -> str:
    """Render templates like ``abbrev`` that take a single term."""
    lang_code = str(template.get(1).value).strip() if template.has(1) else ""
    term = str(template.get(2).value).strip() if template.has(2) else ""
    translation = ""
    if template.has(4):
        translation = str(template.get(4).value).strip()
    elif template.has(3):
        translation = str(template.get(3).value).strip()

    parts: list[str] = []
    if term:
        lemma = mwparserfromhell.parse(term).strip_code()
        parts.append(f"{_lang_template(lang_code)} {_italic(lemma)}".strip())
    if translation:
        gloss = mwparserfromhell.parse(translation).strip_code()
        parts[-1] += f" ({_italic(gloss)})"

    term_part = parts[0] if parts else ""
    return f"{prefix} {term_part}".strip()


def _parse_misc_no_term(_: mwparserfromhell.nodes.Template, text: str) -> str:
    """Return static text for templates without term parameters."""
    return text


def _parse_misc_multiple_terms(
    template: mwparserfromhell.nodes.Template, prefix: str
) -> str:
    """Render templates like ``doublet`` that take multiple term parameters."""
    lang_code = str(template.get(1).value).strip() if template.has(1) else ""
    parts: list[str] = []
    param_index = 2
    term_index = 1
    while template.has(param_index):
        term = str(template.get(param_index).value).strip()
        if term:
            translation_param = f"t{term_index}"
            translation = (
                str(template.get(translation_param).value).strip()
                if template.has(translation_param)
                else ""
            )
            lemma = mwparserfromhell.parse(term).strip_code()
            part = f"{_lang_template(lang_code)} {_italic(lemma)}".strip()
            if translation:
                gloss = mwparserfromhell.parse(translation).strip_code()
                part += f" ({_italic(gloss)})"
            parts.append(part)
            term_index += 1
        param_index += 1
    joined = " and ".join(parts)
    return f"{prefix} {joined}".strip()


_PARSERS: Dict[str, Callable[[mwparserfromhell.nodes.Template], str]] = {
    "af": parse_affix,
    "affix": parse_affix,
    "inh": _parse_inh_der_bor,
    "inherited": _parse_inh_der_bor,
    "der": _parse_inh_der_bor,
    "derived": _parse_inh_der_bor,
    "bor": _parse_inh_der_bor,
    "borrowed": _parse_inh_der_bor,
    "bor+": _parse_inh_der_bor,
    "uder": _parse_inh_der_bor,
    "cog": parse_cognate,
    "cognate": parse_cognate,
    "ncog": parse_noncognate,
    "noncognate": parse_noncognate,
    # Specialized borrowings
    "lbor": lambda tpl: _parse_with_prefix(tpl, "learned borrowing from"),
    "slbor": lambda tpl: _parse_with_prefix(tpl, "semi-learned borrowing from"),
    "obor": lambda tpl: _parse_with_prefix(tpl, "orthographic borrowing from"),
    "ubor": lambda tpl: _parse_with_prefix(tpl, "unadapted borrowing from"),
    "abor": lambda tpl: _parse_with_prefix(tpl, "adapted borrowing from"),
    "cal": lambda tpl: _parse_with_prefix(tpl, "calque of"),
    "clq": lambda tpl: _parse_with_prefix(tpl, "calque of"),
    "pcal": lambda tpl: _parse_with_prefix(tpl, "partial calque of"),
    "pclq": lambda tpl: _parse_with_prefix(tpl, "partial calque of"),
    "sl": lambda tpl: _parse_with_prefix(tpl, "semantic loan from"),
    "psm": lambda tpl: _parse_with_prefix(tpl, "phono-semantic matching of"),
    "translit": lambda tpl: _parse_with_prefix(tpl, "transliteration of"),
    "transliteration": lambda tpl: _parse_with_prefix(tpl, "transliteration of"),
    # Misc templates with one term
    "abbrev": lambda tpl: _parse_misc_single_term(tpl, "Abbreviation of"),
    "abbreviation": lambda tpl: _parse_misc_single_term(tpl, "Abbreviation of"),
    "acronym": lambda tpl: _parse_misc_single_term(tpl, "Acronym of"),
    "back-formation": lambda tpl: _parse_misc_single_term(tpl, "Back-formation from"),
    "clipping": lambda tpl: _parse_misc_single_term(tpl, "Clipping of"),
    "ellipsis": lambda tpl: _parse_misc_single_term(tpl, "Ellipsis of"),
    "initialism": lambda tpl: _parse_misc_single_term(tpl, "Initialism of"),
    "rebracketing": lambda tpl: _parse_misc_single_term(tpl, "Rebracketing of"),
    "reduplication": lambda tpl: _parse_misc_single_term(tpl, "Reduplication of"),
    "spoonerism": lambda tpl: _parse_misc_single_term(tpl, "Spoonerism of"),
    # Misc templates with no term
    "onomatopoeic": lambda tpl: _parse_misc_no_term(tpl, "Onomatopoeic"),
    "uncertain": lambda tpl: _parse_misc_no_term(tpl, "Uncertain"),
    "unknown": lambda tpl: _parse_misc_no_term(tpl, "Unknown"),
    # Misc templates with multiple terms
    "doublet": lambda tpl: _parse_misc_multiple_terms(tpl, "Doublet of"),
    "dbt": lambda tpl: _parse_misc_multiple_terms(tpl, "Doublet of"),
    "piecewise doublet": lambda tpl: _parse_misc_multiple_terms(tpl, "Piecewise doublet of"),
    "pw dbt": lambda tpl: _parse_misc_multiple_terms(tpl, "Piecewise doublet of"),
    "pw_dbt": lambda tpl: _parse_misc_multiple_terms(tpl, "Piecewise doublet of"),
}


def render_template(template: mwparserfromhell.nodes.Template) -> str:
    """Return the rendered representation of an etymology ``template``.

    Unknown templates return an empty string so that they are simply
    removed from the final output.
    """
    name = template.name.strip().lower()
    parser = _PARSERS.get(name)
    if parser:
        return parser(template)
    return ""

__all__ = ["render_template"]
