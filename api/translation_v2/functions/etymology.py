"""Deterministic English-to-Malagasy etymology translation rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from logging import getLogger
from typing import Sequence

import mwparserfromhell
import requests
from api.servicemanager.nllb import (
    DefinitionTranslationError,
    NllbDefinitionTranslation,
)
from api.servicemanager.pgrest import BackendError, JsonDictionary
from conf.entryprocessor.languagecodes.en import LANGUAGE_CODES

from .etymology_rules import (
    CONNECTOR_RULES as _CONNECTOR_RULES,
    DISPLAY_PARAMETERS as _DISPLAY_PARAMETERS,
    ETYMOLOGY_LANGUAGE_CODES as _ETYMOLOGY_LANGUAGE_CODES,
    FORM_DERIVATION_TRANSLATIONS as _FORM_DERIVATION_TRANSLATIONS,
    GLOSSARY_TRANSLATIONS as _GLOSSARY_TRANSLATIONS,
    IGNORED_TEMPLATES as _IGNORED_TEMPLATES,
    LANGUAGE_CODE_ALIASES as _LANGUAGE_CODE_ALIASES,
    MORPHOLOGY_RELATIONS as _MORPHOLOGY_RELATIONS,
    NON_GOVERNING_RULES as _NON_GOVERNING_RULES,
    ORIGIN_RELATIONS as _ORIGIN_RELATIONS,
    REJECTED_TEMPLATES as _REJECTED_TEMPLATES,
    SINGLE_TERM_RELATIONS as _SINGLE_TERM_RELATIONS,
    STANDALONE_TEXT_RULES as _STANDALONE_TEXT_RULES,
    STATIC_TEMPLATE_TRANSLATIONS as _STATIC_TEMPLATE_TRANSLATIONS,
    TEXT_RULES as _TEXT_RULES,
)


class _AtomRole(Enum):
    """Semantic role assigned before connective prose is parsed."""

    TERM = "term"
    RELATION = "relation"
    ROOT = "root"
    ARABIC_ROOT = "arabic_root"
    ELATIVE_FORM = "elative"
    ACTIVE_PARTICIPLE_FORM = "active_participle"


@dataclass(frozen=True)
class _Atom:
    """Wikitext that is opaque to the connective-text translator."""

    text: str
    standalone: str | None = None
    companion_side: str | None = None
    can_complete_operand: bool = True
    role: _AtomRole = _AtomRole.TERM
    language: str | None = None

    @property
    def requires_companion(self) -> bool:
        """Return whether this atom is incomplete without an adjacent term."""

        return self.companion_side is not None


@dataclass(frozen=True)
class _FormDerivationClause:
    """A grammatical form derived from one base and one lexical root."""

    form: _AtomRole
    base: _Atom
    root: _Atom
    terminal: str


_MARKER_START = "\ue000"
_MARKER_END = "\ue001"
_MARKER_RE = re.compile(f"{_MARKER_START}(\\d+){_MARKER_END}")
_ONLY_MARKER_RE = re.compile(
    f"^\\s*{_MARKER_START}(\\d+){_MARKER_END}\\s*([.!?]?)\\s*$"
)
_FORM_DERIVATION_RE = re.compile(
    f"^{_MARKER_START}(?P<form>\\d+){_MARKER_END} "
    f"of(?P<verb> the verb)? {_MARKER_START}(?P<base>\\d+){_MARKER_END}, "
    f"from the root {_MARKER_START}(?P<root>\\d+){_MARKER_END}"
    r"(?P<terminal>[.!?]?)$"
)
_ITALIC_RE = re.compile(r"(?P<marks>'{2,5})(?P<body>.+?)(?P=marks)", re.DOTALL)
_SAFE_TEXT_RE = re.compile(
    r"(?:\s+|[0-9]+(?:[./:-][0-9]+)*|[.,;:!?()[\]/+<>=#*~\-]+|"
    r"[\u2190-\u21ff\u2010-\u2015]+)"
)
_NUMBER_OPERAND_RE = re.compile(r"[0-9]+(?:[./:-][0-9]+)*")
_BAD_PUNCTUATION_RE = re.compile(r"[,;]\s*[,.;!?]|[.!?]\s*[,;]")
_FORMATTING_TAG_RE = re.compile(
    r"</?(?:b|big|i|small|sub|sup)>", re.IGNORECASE
)
_TAG_LIKE_RE = re.compile(r"</?[A-Za-z][^<>]*(?:>|$)")
_BEHAVIOR_SWITCH_RE = re.compile(r"__[A-Z][A-Z0-9_]*__", re.IGNORECASE)
_ACTIVE_WIKITEXT_RE = re.compile(
    r"\{\{|\}\}|\[\[|\]\]|__[A-Z][A-Z0-9_]*__",
    re.IGNORECASE,
)
_DOTTED_LANGUAGE_CODES = {
    "AE.",
    "AG.",
    "BE.",
    "CF.",
    "CL.",
    "EL.",
    "LL.",
    "MIr.",
    "ML.",
    "NL.",
    "OIr.",
    "ONF.",
    "RL.",
    "VG.",
    "VL.",
}
_TRUSTED_LANGUAGE_CODES = (
    frozenset(LANGUAGE_CODES)
    | _ETYMOLOGY_LANGUAGE_CODES
    | _DOTTED_LANGUAGE_CODES
)
# Mirrors Wiktionary's ``if-ar-lect`` sem-arb family contract.
_ARABIC_LECT_CODES = frozenset(
    {
        "abh",
        "abv",
        "acm",
        "acw",
        "acx",
        "acy",
        "adf",
        "aeb",
        "afb",
        "ajp",
        "apc",
        "apd",
        "ar",
        "arq",
        "ars",
        "ary",
        "arz",
        "auz",
        "ayl",
        "ayn",
        "ayp",
        "mt",
        "shu",
        "sqr",
        "ssh",
        "xaa",
    }
)
_MAX_PARAMETER_INDEX_DIGITS = 6
_MAX_SECTION_LENGTH = 10_000
_MAX_SECTIONS = 32
_MAX_BATCH_LENGTH = 50_000
_TRANSLATED_GLOSS_RE = re.compile(r"\(midika hoe ''(?P<gloss>.*?)''\)")

log = getLogger(__name__)
json_dictionary = JsonDictionary(use_materialised_view=False)


def _valid_gloss_translation(gloss: str, translation: object) -> str | None:
    """Return a safe translated gloss that differs from its English source."""

    if not isinstance(translation, str):
        return None
    translation = re.sub(r"\s+", " ", translation).strip(" .")
    if (
        not translation
        or translation.casefold() == gloss.strip(" .").casefold()
        or _ACTIVE_WIKITEXT_RE.search(translation)
        or "''" in translation
        or len(translation) > max(len(gloss) * 3, len(gloss) + 20)
    ):
        return None
    return translation


def _dictionary_gloss_translation(gloss: str) -> str | None:
    """Return the first Malagasy dictionary definition for an English gloss."""

    if not json_dictionary.online:
        return None
    for part_of_speech in ("ana", "mat", "mpam", "tamb"):
        try:
            rows = json_dictionary.look_up_dictionary("en", part_of_speech, gloss)
        except (BackendError, requests.RequestException, ValueError) as exc:
            log.warning("Unable to look up etymology gloss %r: %s", gloss, exc)
            return None
        if not isinstance(rows, list):
            continue
        for row in rows:
            definitions = row.get("definitions", []) if isinstance(row, dict) else []
            if not isinstance(definitions, list):
                continue
            for definition in definitions:
                if (
                    not isinstance(definition, dict)
                    or definition.get("language") != "mg"
                ):
                    continue
                translation = _valid_gloss_translation(
                    gloss,
                    definition.get("definition"),
                )
                if translation is not None:
                    return translation
    return None


def _translate_glosses_in_etymology(text: str) -> str:
    """Translate generated English glosses with dictionary and NLLB fallbacks."""

    nllb: NllbDefinitionTranslation | None = None

    def replace(match: re.Match[str]) -> str:
        nonlocal nllb
        gloss = match.group("gloss")
        translation = _dictionary_gloss_translation(gloss)
        if translation is None:
            nllb = nllb or NllbDefinitionTranslation(
                source_language="en",
                target_language="mg",
            )
            try:
                translation = _valid_gloss_translation(
                    gloss,
                    nllb.get_translation(gloss),
                )
            except (
                DefinitionTranslationError,
                KeyError,
                requests.RequestException,
                TypeError,
                ValueError,
            ) as exc:
                log.warning("Unable to translate etymology gloss %r: %s", gloss, exc)

        if translation is None:
            return f"(midika hoe ''{gloss}'' amin'ny teny anglisy)"
        return f"(midika hoe ''{translation}'' (anglisy: ''{gloss}''))"

    return _TRANSLATED_GLOSS_RE.sub(replace, text)


def _normalise_template_name(template: mwparserfromhell.nodes.Template) -> str:
    """Return a case-insensitive, separator-normalised template name."""

    return re.sub(r"[\s_-]+", " ", str(template.name).strip()).casefold()


def _parameter(
    template: mwparserfromhell.nodes.Template, key: str | int
) -> str:
    """Return a stripped template parameter or an empty string."""

    if not template.has(key):
        return ""
    return str(template.get(key).value).strip()


def _parameters_are_supported(
    template: mwparserfromhell.nodes.Template,
    *,
    named: set[str],
    numbered: set[str] | None = None,
    maximum_position: int | None = None,
) -> bool:
    """Return whether every non-empty parameter has defined semantics."""

    numbered = numbered or set()
    for parameter in template.params:
        raw_key = str(parameter.name).strip()
        key = raw_key.casefold()
        value = str(parameter.value).strip()
        if not value:
            continue
        if not _parameter_markup_is_safe(value):
            return False
        if key.isdigit():
            if (
                len(key) > _MAX_PARAMETER_INDEX_DIGITS
                or key == "0"
                or (len(key) > 1 and key.startswith("0"))
            ):
                return False
            if maximum_position is not None and int(key) > maximum_position:
                return False
            continue
        match = re.fullmatch(r"([a-z]+)(\d+)", key)
        if (
            raw_key != key
            or (
                match
                and (
                    len(match.group(2)) > _MAX_PARAMETER_INDEX_DIGITS
                    or match.group(2).startswith("0")
                )
            )
        ):
            return False
        if key not in named and (match is None or match.group(1) not in numbered):
            return False
    return True


def _parameter_markup_is_safe(value: str) -> bool:
    """Allow balanced formatting tags but reject active or lossy markup."""

    code = mwparserfromhell.parse(value)
    if (
        code.filter_templates()
        or code.filter_external_links()
        or code.filter_comments()
        or _has_forbidden_wikilink(code)
    ):
        return False

    stack: list[str] = []
    for match in _FORMATTING_TAG_RE.finditer(value):
        tag = match.group(0)
        name = tag.strip("</>").casefold()
        if tag.startswith("</"):
            if not stack or stack.pop() != name:
                return False
        else:
            stack.append(name)
    without_formatting = _FORMATTING_TAG_RE.sub("", value)
    normalised = code.strip_code().strip()
    return (
        not stack
        and _TAG_LIKE_RE.search(without_formatting) is None
        and _BEHAVIOR_SWITCH_RE.search(value) is None
        and _ACTIVE_WIKITEXT_RE.search(normalised) is None
        and _TAG_LIKE_RE.search(normalised) is None
    )


def _numbered_parameters_fit_components(
    template: mwparserfromhell.nodes.Template,
    component_count: int,
    semantic_names: set[str],
) -> bool:
    """Reject semantic annotations that do not belong to a component."""

    for parameter in template.params:
        key = str(parameter.name).strip().casefold()
        match = re.fullmatch(r"([a-z]+)(\d+)", key)
        if (
            match
            and match.group(1) in semantic_names
            and str(parameter.value).strip()
            and len(match.group(2)) <= _MAX_PARAMETER_INDEX_DIGITS
            and int(match.group(2)) > component_count
        ):
            return False
    return True


def _plain(value: str) -> str:
    """Remove nested wiki markup from a term or gloss."""

    if not value:
        return ""
    plain = mwparserfromhell.parse(value).strip_code().strip()
    if value.lstrip().startswith("*") and not plain.startswith("*"):
        plain = "*" + plain
    return plain


def _italic(value: str) -> str:
    """Render a non-empty value with wiki italics."""

    if not value:
        return ""
    if value.startswith("'") or value.endswith("'") or "''" in value:
        return f"<i>{value}</i>"
    return f"''{value}''"


def _language(code: str) -> str:
    """Render a Wiktionary language-code template."""

    code = code.strip()
    code = _LANGUAGE_CODE_ALIASES.get(code, code)
    if code not in _TRUSTED_LANGUAGE_CODES:
        return ""
    return f"{{{{{code}}}}}"


def _has_valid_language(
    template: mwparserfromhell.nodes.Template,
    key: str | int,
    *,
    required: bool = True,
) -> bool:
    """Return whether a language parameter is present and syntactically valid."""

    code = _parameter(template, key)
    return (not required and not code) or bool(_language(code))


def _has_contiguous_components(indexes: list[int]) -> bool:
    """Return whether term slots start at two and contain no gaps."""

    return indexes == list(range(2, len(indexes) + 2))


def _trim_trailing_empty_components(
    template: mwparserfromhell.nodes.Template,
    indexes: list[int],
) -> list[int]:
    """Ignore explicit trailing placeholders that carry no metadata."""

    indexes = list(indexes)
    annotation_names = (
        "alt",
        "g",
        "gloss",
        "lang",
        "lit",
        "pos",
        "q",
        "qq",
        "t",
        "tr",
        "ts",
    )
    while indexes:
        component_number = indexes[-1] - 1
        if _parameter(template, indexes[-1]) or any(
            _parameter(template, f"{name}{component_number}")
            for name in annotation_names
        ):
            break
        indexes.pop()
    return indexes


def _first_parameter(
    template: mwparserfromhell.nodes.Template, *keys: str | int
) -> str:
    """Return the first non-empty parameter listed in ``keys``."""

    for key in keys:
        value = _parameter(template, key)
        if value:
            return value
    return ""


def _joined_parameters(
    template: mwparserfromhell.nodes.Template, *keys: str | int
) -> str:
    """Join all non-empty parameter values without discarding aliases."""

    return ", ".join(
        value for key in keys if (value := _parameter(template, key))
    )


def _parameters_conflict(
    template: mwparserfromhell.nodes.Template, *keys: str | int
) -> bool:
    """Return whether aliases provide more than one competing value."""

    return sum(bool(_parameter(template, key)) for key in keys) > 1


def _standalone_text(
    template: mwparserfromhell.nodes.Template,
    rendered: str,
    default: str,
) -> str:
    """Honor a template's request to suppress its relation text."""

    notext = _parameter(template, "notext").casefold()
    if notext and notext not in {"0", "false", "n", "no"}:
        return rendered
    return default


def _render_term(
    language_code: str,
    term: str,
    *,
    transliteration: str = "",
    transcription: str = "",
    gloss: str = "",
    literal: str = "",
    position: str = "",
    gender: str = "",
    qualifier: str = "",
) -> str:
    """Render one etymon while keeping lexical content opaque."""

    language_markup = _language(language_code)
    if language_code and not language_markup:
        return ""
    pieces = [language_markup] if language_markup else []
    plain_term = _plain(term)
    if term and term != "-" and not plain_term:
        return ""
    if plain_term and plain_term != "-":
        pieces.append(_italic(plain_term))
    rendered = " ".join(pieces)

    plain_transliteration = _plain(transliteration)
    if plain_transliteration and plain_transliteration != "-":
        rendered += f" (soratana hoe {_italic(plain_transliteration)})"
    plain_transcription = _plain(transcription)
    if plain_transcription and plain_transcription != "-":
        rendered += f" (tononina hoe {_italic(plain_transcription)})"
    plain_gloss = _plain(gloss)
    if plain_gloss:
        rendered += f" (midika hoe {_italic(plain_gloss)})"
    plain_literal = _plain(literal)
    if plain_literal:
        rendered += f" (ara-bakiteny hoe {_italic(plain_literal)})"
    plain_position = _plain(position)
    if plain_position:
        rendered += f" (sokajy: {_italic(plain_position)})"
    plain_gender = _plain(gender)
    if plain_gender:
        rendered += f" (fitsipi-pitenenana: {_italic(plain_gender)})"
    plain_qualifier = _plain(qualifier)
    if plain_qualifier:
        rendered += f" (fanamarihana: {_italic(plain_qualifier)})"
    return rendered.strip()


def _render_origin_template(
    template: mwparserfromhell.nodes.Template, relation: str
) -> _Atom | None:
    """Render inheritance, derivation, and borrowing templates."""

    if not _parameters_are_supported(
        template,
        named=_DISPLAY_PARAMETERS
        | {"alt", "g", "g2", "gloss", "lit", "pos", "q", "qq", "t", "tr", "ts"},
        maximum_position=5,
    ):
        return None
    if not _has_valid_language(template, 1) or not _has_valid_language(
        template, 2
    ):
        return None
    if _parameters_conflict(template, "t", "gloss"):
        return None
    named_gloss = _first_parameter(template, "t", "gloss")
    positional_five = _parameter(template, 5)
    if named_gloss and positional_five:
        return None
    rendered = _render_term(
        _parameter(template, 2),
        _first_parameter(template, "alt", 4, 3),
        transliteration=_parameter(template, "tr"),
        transcription=_parameter(template, "ts"),
        gloss=named_gloss or positional_five,
        literal=_parameter(template, "lit"),
        position=_parameter(template, "pos"),
        gender=_joined_parameters(template, "g", "g2"),
        qualifier=_joined_parameters(template, "q", "qq"),
    )
    if not rendered:
        return None
    standalone = _ORIGIN_RELATIONS[relation].format(term=rendered)
    return _Atom(
        rendered,
        _standalone_text(template, rendered, standalone),
        role=_AtomRole.RELATION,
    )


def _render_mention_template(
    template: mwparserfromhell.nodes.Template,
    *,
    allow_language_only: bool = False,
) -> _Atom | None:
    """Render mention, link, and cognate templates."""

    if not _parameters_are_supported(
        template,
        named=_DISPLAY_PARAMETERS
        | {"alt", "g", "g1", "g2", "gloss", "lit", "pos", "q", "qq", "t", "tr", "ts"},
        maximum_position=4,
    ):
        return None
    if not _has_valid_language(template, 1):
        return None
    if _parameters_conflict(template, "t", "gloss"):
        return None
    named_gloss = _first_parameter(template, "t", "gloss")
    positional_gloss = _parameter(template, 4)
    if named_gloss and positional_gloss:
        return None
    term = _first_parameter(template, "alt", 3, 2)
    has_metadata = any(
        (
            _parameter(template, "tr"),
            _parameter(template, "ts"),
            named_gloss,
            positional_gloss,
            _parameter(template, "lit"),
            _parameter(template, "pos"),
            _joined_parameters(template, "g", "g1", "g2"),
            _joined_parameters(template, "q", "qq"),
        )
    )
    language_only = not term and not has_metadata
    if language_only and not allow_language_only:
        return None
    rendered = _render_term(
        _parameter(template, 1),
        term,
        transliteration=_parameter(template, "tr"),
        transcription=_parameter(template, "ts"),
        gloss=named_gloss or positional_gloss,
        literal=_parameter(template, "lit"),
        position=_parameter(template, "pos"),
        gender=_joined_parameters(template, "g", "g1", "g2"),
        qualifier=_joined_parameters(template, "q", "qq"),
    )
    return (
        _Atom(
            rendered,
            companion_side="right" if language_only else None,
            language=_parameter(template, 1),
        )
        if rendered
        else None
    )


def _numeric_parameter_indexes(
    template: mwparserfromhell.nodes.Template, minimum: int
) -> list[int]:
    """Return sorted positional parameter indexes from ``minimum`` onward."""

    indexes: set[int] = set()
    for parameter in template.params:
        key = str(parameter.name).strip()
        if not key.isdigit() or len(key) > _MAX_PARAMETER_INDEX_DIGITS:
            continue
        index = int(key)
        if index >= minimum:
            indexes.add(index)
    return sorted(indexes)


def _render_affix_template(
    template: mwparserfromhell.nodes.Template, relation: str
) -> _Atom | None:
    """Render affix, compound, and blend templates as component expressions."""

    if not _parameters_are_supported(
        template,
        named=_DISPLAY_PARAMETERS | {"lit", "pos"},
        numbered={
            "alt",
            "g",
            "gloss",
            "id",
            "lang",
            "lit",
            "pos",
            "q",
            "qq",
            "sc",
            "t",
            "tr",
            "ts",
        },
    ):
        return None
    raw_indexes = _numeric_parameter_indexes(template, 2)
    indexes = _trim_trailing_empty_components(template, raw_indexes)
    omitted_prefix_base = relation == "prefix" and indexes != raw_indexes
    if not _has_valid_language(template, 1) or not _has_contiguous_components(
        indexes
    ):
        return None
    if not _numbered_parameters_fit_components(
        template,
        len(indexes),
        {"alt", "g", "gloss", "lang", "lit", "pos", "q", "qq", "t", "tr", "ts"},
    ):
        return None
    components: list[str] = []
    for parameter_index in indexes:
        component_number = parameter_index - 1
        raw_component = _first_parameter(
            template, f"alt{component_number}", parameter_index
        )
        component = _plain(raw_component)
        if not component:
            has_annotations = any(
                _parameter(template, f"{name}{component_number}")
                for name in (
                    "alt",
                    "g",
                    "gloss",
                    "lang",
                    "lit",
                    "pos",
                    "q",
                    "qq",
                    "t",
                    "tr",
                    "ts",
                )
            )
            if has_annotations or relation in {"blend", "com", "compound"}:
                return None
            continue
        if _parameters_conflict(
            template,
            f"t{component_number}",
            f"gloss{component_number}",
        ):
            return None
        if relation == "prefix" and (
            omitted_prefix_base or parameter_index != indexes[-1]
        ):
            component = component.rstrip("-") + "-"
        elif relation in {"suf", "suffix"} and parameter_index != indexes[0]:
            component = "-" + component.lstrip("-")

        language_code = _parameter(template, f"lang{component_number}")
        rendered_component = (
            component
            if component.startswith("-") or component.endswith("-")
            else _italic(component)
        )
        if language_code:
            language_markup = _language(language_code)
            if not language_markup:
                return None
            rendered_component = f"{language_markup} {rendered_component}"
        annotation = _render_term(
            "",
            "",
            transliteration=_parameter(template, f"tr{component_number}"),
            transcription=_parameter(template, f"ts{component_number}"),
            gloss=_first_parameter(
                template, f"t{component_number}", f"gloss{component_number}"
            ),
            literal=_parameter(template, f"lit{component_number}"),
            position=_parameter(template, f"pos{component_number}"),
            gender=_parameter(template, f"g{component_number}"),
            qualifier=_joined_parameters(
                template, f"q{component_number}", f"qq{component_number}"
            ),
        )
        if annotation:
            rendered_component += f" {annotation}"
        components.append(rendered_component)

    if not components:
        return None
    if relation in {"blend", "com", "compound"} and len(components) < 2:
        return None
    rendered = " + ".join(components)
    whole_annotation = _render_term(
        "",
        "",
        literal=_parameter(template, "lit"),
        position=_parameter(template, "pos"),
    )
    if whole_annotation:
        rendered += f" {whole_annotation}"
    requires_companion = len(components) < 2
    standalone = (
        _MORPHOLOGY_RELATIONS[relation].format(term=rendered)
        if not requires_companion
        else None
    )
    if standalone is not None:
        standalone = _standalone_text(template, rendered, standalone)
    companion_side = None
    if requires_companion:
        if rendered.startswith("-"):
            companion_side = "left"
        elif relation in {"prefix", "suf", "suffix"} or rendered.endswith("-"):
            companion_side = "right"
        else:
            return None
    return _Atom(rendered, standalone, companion_side)


def _render_root_template(
    template: mwparserfromhell.nodes.Template, name: str
) -> _Atom | None:
    """Render generic, Arabic, and Hebrew root templates."""

    if not _parameters_are_supported(
        template,
        named=_DISPLAY_PARAMETERS | {"gloss", "lit", "t", "tr", "ts"},
        numbered={"id"},
    ):
        return None
    if name == "root":
        if not _has_valid_language(template, 1) or not _has_valid_language(
            template, 2
        ):
            return None
        language_code = _parameter(template, 2)
        roots = [
            _italic(_plain(_parameter(template, index)))
            for index in _numeric_parameter_indexes(template, 3)
            if _plain(_parameter(template, index))
        ]
    else:
        language_code = "ar" if name == "ar root" else "he"
        raw_roots = [
            _plain(_parameter(template, index))
            for index in _numeric_parameter_indexes(template, 1)
        ]
        combined_root = " ".join(root for root in raw_roots if root)
        roots = [_italic(combined_root)] if combined_root else []

    if not roots:
        return None
    if _parameters_conflict(template, "t", "gloss"):
        return None
    language_markup = _language(language_code)
    if language_code and not language_markup:
        return None
    rendered_roots = " sy ".join(roots)
    rendered = " ".join(
        part for part in (language_markup, rendered_roots) if part
    )
    annotation = _render_term(
        "",
        "",
        transliteration=_parameter(template, "tr"),
        transcription=_parameter(template, "ts"),
        gloss=_first_parameter(template, "t", "gloss"),
        literal=_parameter(template, "lit"),
    )
    if annotation:
        rendered += f" {annotation}"
    standalone = f"Avy amin'ny fototeny {rendered}"
    return _Atom(
        rendered,
        _standalone_text(template, rendered, standalone),
        role=(
            _AtomRole.ARABIC_ROOT
            if name == "ar root"
            else _AtomRole.ROOT
        ),
    )


def _render_single_term_template(
    template: mwparserfromhell.nodes.Template, relation: str
) -> _Atom | None:
    """Render a relation template containing one source term."""

    if not _parameters_are_supported(
        template,
        named=_DISPLAY_PARAMETERS
        | {"alt", "g", "gloss", "lit", "pos", "q", "qq", "t", "tr", "ts"},
        maximum_position=4,
    ):
        return None
    if not _has_valid_language(template, 1):
        return None
    if _parameters_conflict(template, "t", "gloss"):
        return None
    named_gloss = _first_parameter(template, "t", "gloss")
    positional_gloss = _parameter(template, 4)
    if named_gloss and positional_gloss:
        return None
    rendered = _render_term(
        _parameter(template, 1),
        _first_parameter(template, "alt", 3, 2),
        transliteration=_parameter(template, "tr"),
        transcription=_parameter(template, "ts"),
        gloss=named_gloss or positional_gloss,
        literal=_parameter(template, "lit"),
        position=_parameter(template, "pos"),
        gender=_parameter(template, "g"),
        qualifier=_joined_parameters(template, "q", "qq"),
    )
    if not rendered:
        return None
    standalone = _SINGLE_TERM_RELATIONS[relation].format(term=rendered)
    return _Atom(rendered, _standalone_text(template, rendered, standalone))


def _render_doublet_template(
    template: mwparserfromhell.nodes.Template, piecewise: bool
) -> _Atom | None:
    """Render a doublet template containing one or more terms."""

    if not _parameters_are_supported(
        template,
        named=_DISPLAY_PARAMETERS,
        numbered={"alt", "g", "gloss", "id", "lit", "pos", "q", "qq", "t", "tr", "ts"},
    ):
        return None
    language_code = _parameter(template, 1)
    term_indexes = _numeric_parameter_indexes(template, 2)
    if not _has_valid_language(template, 1) or not _has_contiguous_components(
        term_indexes
    ):
        return None
    if not _numbered_parameters_fit_components(
        template,
        len(term_indexes),
        {"alt", "g", "gloss", "lit", "pos", "q", "qq", "t", "tr", "ts"},
    ):
        return None
    terms: list[str] = []
    for parameter_index in term_indexes:
        term_number = parameter_index - 1
        if _parameters_conflict(
            template,
            f"t{term_number}",
            f"gloss{term_number}",
        ):
            return None
        rendered = _render_term(
            language_code,
            _first_parameter(template, f"alt{term_number}", parameter_index),
            transliteration=_parameter(template, f"tr{term_number}"),
            transcription=_parameter(template, f"ts{term_number}"),
            gloss=_first_parameter(
                template, f"t{term_number}", f"gloss{term_number}"
            ),
            literal=_parameter(template, f"lit{term_number}"),
            position=_parameter(template, f"pos{term_number}"),
            gender=_parameter(template, f"g{term_number}"),
            qualifier=_joined_parameters(
                template, f"q{term_number}", f"qq{term_number}"
            ),
        )
        if rendered:
            terms.append(rendered)
    if not terms:
        return None
    rendered_terms = " sy ".join(terms)
    description = (
        "Teny iray fiaviana amin'ny isam-pizarana amin'ny"
        if piecewise
        else "Teny iray fiaviana amin'ny"
    )
    standalone = f"{description} {rendered_terms}"
    return _Atom(
        rendered_terms,
        _standalone_text(template, rendered_terms, standalone),
    )


def _render_template(
    template: mwparserfromhell.nodes.Template,
) -> _Atom | None:
    """Render a supported source template, returning ``None`` if unsafe."""

    name = _normalise_template_name(template)
    if name in _ORIGIN_RELATIONS:
        return _render_origin_template(template, name)
    if name in {"m", "mention", "l", "link", "ll", "cog", "cognate"}:
        atom = _render_mention_template(
            template,
            allow_language_only=name in {"cog", "cognate"},
        )
        if atom and name in {"cog", "cognate"}:
            if atom.requires_companion:
                return atom
            standalone = f"Mitovy fiaviana amin'ny {atom.text}"
            return _Atom(
                atom.text,
                _standalone_text(template, atom.text, standalone),
                role=_AtomRole.RELATION,
            )
        return atom
    if name in {"ncog", "noncog", "noncognate"}:
        atom = _render_mention_template(template)
        if atom is None:
            return None
        standalone = f"Tsy mitovy fiaviana amin'ny {atom.text}"
        return _Atom(
            atom.text,
            _standalone_text(template, atom.text, standalone),
            role=_AtomRole.RELATION,
        )
    if name in _MORPHOLOGY_RELATIONS:
        return _render_affix_template(template, name)
    if name in {"root", "ar root", "he root"}:
        return _render_root_template(template, name)
    if name == "etyl":
        if not _parameters_are_supported(
            template, named=_DISPLAY_PARAMETERS, maximum_position=2
        ) or not _has_valid_language(template, 2):
            return None
        rendered = _language(_parameter(template, 1))
        return _Atom(rendered, companion_side="right") if rendered else None
    if name == "ltc l":
        if not _parameters_are_supported(
            template,
            named=_DISPLAY_PARAMETERS | {"gloss", "lit", "t", "tr", "ts"},
            maximum_position=3,
        ):
            return None
        if (
            _parameters_conflict(template, "t", "gloss")
            or (_parameter(template, 2) and _parameter(template, 3))
        ):
            return None
        named_gloss = _first_parameter(template, "t", "gloss")
        positional_gloss = _first_parameter(template, 3, 2)
        if named_gloss and positional_gloss:
            return None
        rendered = _render_term(
            "ltc",
            _parameter(template, 1),
            transliteration=_parameter(template, "tr"),
            transcription=_parameter(template, "ts"),
            gloss=named_gloss or positional_gloss,
            literal=_parameter(template, "lit"),
        )
        return _Atom(rendered) if rendered else None
    if name in _SINGLE_TERM_RELATIONS:
        return _render_single_term_template(template, name)
    if name in {"ar active participle", "ar elative"}:
        is_active_participle = name == "ar active participle"
        if not _parameters_are_supported(
            template,
            named=(
                {"lc", "nocap", "nocat", "noderived"}
                if is_active_participle
                else {"lc", "nocap", "nocat"}
            ),
            maximum_position=1 if is_active_participle else 0,
        ):
            return None
        language = _parameter(template, 1) or "ar"
        if language not in _ARABIC_LECT_CODES:
            return None
        role = (
            _AtomRole.ACTIVE_PARTICIPLE_FORM
            if is_active_participle
            else _AtomRole.ELATIVE_FORM
        )
        return _Atom(
            "",
            can_complete_operand=False,
            role=role,
            language=language,
        )
    if name == "deverbal":
        if not _parameters_are_supported(
            template,
            named=_DISPLAY_PARAMETERS
            | {"alt", "g", "gloss", "lit", "pos", "q", "qq", "t", "tr", "ts"},
            maximum_position=4,
        ):
            return None
        if not _has_valid_language(template, 1):
            return None
        if _parameters_conflict(template, "t", "gloss"):
            return None
        named_gloss = _first_parameter(template, "t", "gloss")
        positional_gloss = _parameter(template, 4)
        if named_gloss and positional_gloss:
            return None
        rendered = _render_term(
            _parameter(template, 1),
            _first_parameter(template, "alt", 3, 2),
            transliteration=_parameter(template, "tr"),
            transcription=_parameter(template, "ts"),
            gloss=named_gloss or positional_gloss,
            literal=_parameter(template, "lit"),
            position=_parameter(template, "pos"),
            gender=_parameter(template, "g"),
            qualifier=_joined_parameters(template, "q", "qq"),
        )
        if not rendered:
            return None
        standalone = f"Avy amin'ny matoanteny {rendered}"
        return _Atom(
            rendered,
            _standalone_text(template, rendered, standalone),
        )
    if name in {"doublet", "dbt"}:
        return _render_doublet_template(template, piecewise=False)
    if name in {"piecewise doublet", "pw dbt"}:
        return _render_doublet_template(template, piecewise=True)
    if name in _STATIC_TEMPLATE_TRANSLATIONS:
        if not _parameters_are_supported(
            template,
            named=_DISPLAY_PARAMETERS | {"title"},
            maximum_position=1,
        ):
            return None
        if _parameter(template, 1) and not _has_valid_language(
            template, 1, required=False
        ):
            return None
        title = _plain(_parameter(template, "title")).rstrip(".").casefold()
        static_name = name
        if title:
            if name in {"unknown", "uncertain"} and title in {
                "origin uncertain",
                "uncertain",
            }:
                static_name = "uncertain"
            elif name in {"unknown", "uncertain"} and title in {
                "of unknown origin",
                "origin unknown",
                "unknown",
            }:
                static_name = "unknown"
            else:
                return None
        atom_text, standalone = _STATIC_TEMPLATE_TRANSLATIONS[static_name]
        return _Atom(atom_text, standalone, can_complete_operand=False)
    if name == "unk":
        if not _parameters_are_supported(
            template,
            named=_DISPLAY_PARAMETERS | {"title"},
            maximum_position=1,
        ):
            return None
        if _parameter(template, 1) and not _has_valid_language(
            template, 1, required=False
        ):
            return None
        title = _plain(_parameter(template, "title")).rstrip(".").casefold()
        if not title or title == "unknown":
            atom_text, standalone = _STATIC_TEMPLATE_TRANSLATIONS["unknown"]
        elif title == "uncertain":
            atom_text, standalone = _STATIC_TEMPLATE_TRANSLATIONS["uncertain"]
        else:
            return None
        return _Atom(atom_text, standalone, can_complete_operand=False)
    if name == "glossary":
        if not _parameters_are_supported(
            template, named=set(), maximum_position=1
        ):
            return None
        translated = _GLOSSARY_TRANSLATIONS.get(_plain(_parameter(template, 1)).casefold())
        return _Atom(translated, can_complete_operand=False) if translated else None
    return None


def _protect_italic_text(
    text: str, atoms: list[_Atom], protected: list[str]
) -> bool:
    """Append text while replacing italicised terms with atom markers."""

    position = 0
    for match in _ITALIC_RE.finditer(text):
        if (
            "{" in match.group("body")
            or "}" in match.group("body")
            or not _normalised_text_is_safe(
                match.group("body"), require_visible=True
            )
        ):
            return False
        protected.append(text[position : match.start()])
        atoms.append(
            _Atom(
                match.group(0),
                can_complete_operand=_markup_has_visible_operand(match.group(0)),
            )
        )
        protected.append(f"{_MARKER_START}{len(atoms) - 1}{_MARKER_END}")
        position = match.end()
    protected.append(text[position:])
    return True


def _opaque_markup_is_safe(value: str) -> bool:
    """Reject executable or nested markup inside an otherwise opaque atom."""

    code = mwparserfromhell.parse(value)
    if (
        code.filter_templates()
        or code.filter_external_links()
        or code.filter_comments()
        or _has_forbidden_wikilink(code)
        or not _normalised_text_is_safe(value)
    ):
        return False
    return all(
        str(tag.tag).strip().casefold() in {"b", "i"} and not tag.attributes
        for tag in code.filter_tags()
    )


def _has_forbidden_wikilink(code: mwparserfromhell.wikicode.Wikicode) -> bool:
    """Return whether markup embeds a file, category, or image link."""

    return any(
        str(link.title).strip().casefold().startswith(
            ("category:", "file:", "image:")
        )
        for link in code.filter_wikilinks(recursive=True)
    )


def _normalised_text_is_safe(value: str, *, require_visible: bool = False) -> bool:
    """Reject markup that becomes active only after code stripping."""

    normalised = mwparserfromhell.parse(value).strip_code().strip()
    return (
        (bool(normalised) or not require_visible)
        and _ACTIVE_WIKITEXT_RE.search(normalised) is None
        and _TAG_LIKE_RE.search(normalised) is None
    )


def _italic_contents_are_safe(value: str) -> bool:
    """Allow plain protoform markers while rejecting nested active markup."""

    code = mwparserfromhell.parse(value)
    return (
        not code.filter_templates()
        and not code.filter_external_links()
        and not code.filter_comments()
        and not _has_forbidden_wikilink(code)
        and _normalised_text_is_safe(value, require_visible=True)
        and "{" not in value
        and "}" not in value
        and "<" not in value
        and ">" not in value
    )


def _render_formatting_tag(node: mwparserfromhell.nodes.Tag) -> _Atom | None:
    """Render safe lexical formatting, including wrapped mention templates."""

    name = str(node.tag).strip().casefold()
    if name not in {"b", "i"} or node.attributes:
        return None
    contents = str(node.contents or "")
    if not contents.strip():
        return None
    code = mwparserfromhell.parse(contents)
    if len(code.nodes) == 1 and isinstance(
        code.nodes[0], mwparserfromhell.nodes.Template
    ):
        atom = _render_template(code.nodes[0])
        return atom if atom and atom.standalone is None else None
    if name == "b" and not (
        len(code.nodes) == 1
        and isinstance(code.nodes[0], mwparserfromhell.nodes.Wikilink)
    ):
        return None
    return (
        _Atom(
            str(node),
            can_complete_operand=_markup_has_visible_operand(str(node)),
        )
        if _italic_contents_are_safe(contents)
        else None
    )


def _protect_wikitext(section: str) -> tuple[str, list[_Atom]] | None:
    """Replace supported wikitext nodes with opaque markers."""

    if _MARKER_START in section or _MARKER_END in section:
        return None

    code = mwparserfromhell.parse(section)
    protected: list[str] = []
    atoms: list[_Atom] = []
    for node in code.nodes:
        if isinstance(node, mwparserfromhell.nodes.Text):
            if not _protect_italic_text(str(node), atoms, protected):
                return None
            continue
        if isinstance(node, mwparserfromhell.nodes.Template):
            name = _normalise_template_name(node)
            if name in _IGNORED_TEMPLATES:
                continue
            if name in _REJECTED_TEMPLATES:
                return None
            atom = _render_template(node)
            if atom is None:
                return None
        elif isinstance(node, mwparserfromhell.nodes.Wikilink):
            title = str(node.title).strip().casefold()
            if title.startswith(("file:", "image:", "category:")) or not _opaque_markup_is_safe(
                str(node)
            ):
                return None
            atom = _Atom(
                str(node),
                can_complete_operand=_markup_has_visible_operand(str(node)),
            )
        elif isinstance(node, mwparserfromhell.nodes.Tag):
            if str(node.tag).strip().casefold() == "ref":
                continue
            atom = _render_formatting_tag(node)
            if atom is None:
                return None
        elif isinstance(node, mwparserfromhell.nodes.Comment):
            continue
        elif isinstance(node, mwparserfromhell.nodes.HTMLEntity):
            atom = _Atom(
                str(node),
                can_complete_operand=_markup_has_visible_operand(str(node)),
            )
        else:
            return None

        atoms.append(atom)
        protected.append(f"{_MARKER_START}{len(atoms) - 1}{_MARKER_END}")
    return "".join(protected), atoms


def _matches_rule(text: str, position: int, source: str) -> bool:
    """Return whether a literal rule starts at a word boundary."""

    if (
        not text.startswith(source, position)
        or (
            position > 0
            and not text[position - 1].isspace()
            and text[position - 1] not in ",.;:!?()[]/+"
        )
    ):
        return False
    end = position + len(source)
    return end == len(text) or text[end].isspace() or text[end] in ",.;:!?()[]/+"


def _delimiters_are_balanced(text: str) -> bool:
    """Return whether structural parentheses and brackets are balanced."""

    stack: list[str] = []
    closing = {")": "(", "]": "["}
    for character in text:
        if character in "([":
            stack.append(character)
        elif character in closing:
            if not stack or stack.pop() != closing[character]:
                return False
    return not stack


def _parse_form_derivation_clause(
    text: str, atoms: list[_Atom]
) -> tuple[bool, _FormDerivationClause | None]:
    """Parse a fully consumed form/base/root clause into typed relations."""

    form_roles = {
        _AtomRole.ACTIVE_PARTICIPLE_FORM,
        _AtomRole.ELATIVE_FORM,
    }
    referenced_atoms = [
        atoms[int(marker.group(1))]
        for marker in _MARKER_RE.finditer(text)
    ]
    if not any(atom.role in form_roles for atom in referenced_atoms):
        return False, None
    match = _FORM_DERIVATION_RE.fullmatch(text)
    if match is None:
        return True, None
    try:
        form = atoms[int(match.group("form"))]
        base = atoms[int(match.group("base"))]
        root = atoms[int(match.group("root"))]
    except IndexError:
        return True, None
    if (
        form.role not in form_roles
        or base.role is not _AtomRole.TERM
        or base.language != form.language
        or base.requires_companion
        or not base.can_complete_operand
        or root.role is not _AtomRole.ARABIC_ROOT
        or (match.group("verb") and form.role is not _AtomRole.ACTIVE_PARTICIPLE_FORM)
    ):
        return True, None
    return True, _FormDerivationClause(
        form=form.role,
        base=base,
        root=root,
        terminal=match.group("terminal"),
    )


def _finalise_statement(result: str) -> str | None:
    """Normalise and validate one completely rendered statement."""

    result = re.sub(r"\s+", " ", result).strip()
    result = re.sub(r"\s+([,.;:!?])", r"\1", result)
    result = re.sub(r"([([])\s+", r"\1", result)
    result = re.sub(r"\s+([)\]])", r"\1", result)
    result = re.sub(r"(\{\{([^{}|]+)\}\})\s+\1", r"\1", result)
    if (
        not _delimiters_are_balanced(result)
        or result.endswith((",", ";", ":"))
        or re.search(r"[.!?]{2,}$", result)
        or _BAD_PUNCTUATION_RE.search(result)
    ):
        return None
    if result and not result.endswith((".", "?", "!")):
        result += "."
    return result or None


def _render_form_derivation_clause(clause: _FormDerivationClause) -> str | None:
    """Render a validated form derivation through controlled Malagasy rules."""

    template = _FORM_DERIVATION_TRANSLATIONS[clause.form.value]
    return _finalise_statement(
        template.format(base=clause.base.text, root=clause.root.text)
        + clause.terminal
    )


def _has_complete_companion(
    text: str,
    current_marker: re.Match[str],
    atoms: list[_Atom],
) -> bool:
    """Return whether an incomplete atom is paired with lexical content."""

    atom = atoms[int(current_marker.group(1))]
    for marker in _MARKER_RE.finditer(text):
        if (
            marker.start() == current_marker.start()
            or atoms[int(marker.group(1))].requires_companion
            or not atoms[int(marker.group(1))].can_complete_operand
        ):
            continue
        if (
            atom.companion_side == "left"
            and marker.end() <= current_marker.start()
        ):
            separator = text[marker.end() : current_marker.start()]
        elif (
            atom.companion_side == "right"
            and marker.start() >= current_marker.end()
        ):
            separator = text[current_marker.end() : marker.start()]
        else:
            continue
        if re.fullmatch(r"\s*(?:\+\s*)?", separator):
            return True
    return False


def _markup_has_visible_operand(value: str) -> bool:
    """Return whether opaque markup visibly contains lexical content."""

    visible = mwparserfromhell.parse(value).strip_code().strip()
    return any(character.isalnum() for character in visible)


def _translate_statement(text: str, atoms: list[_Atom]) -> str | None:
    """Translate one protected statement when the grammar consumes it all."""

    text = re.sub(r"\s+", " ", text).strip()
    if (
        not text
        or text.startswith((",", ";", ":"))
        or not _delimiters_are_balanced(text)
    ):
        return None

    marker_only = _ONLY_MARKER_RE.fullmatch(text)
    if marker_only:
        atom = atoms[int(marker_only.group(1))]
        if atom.standalone is None:
            return None
        punctuation = marker_only.group(2) or "."
        return atom.standalone.rstrip(".!?") + punctuation

    owns_form_clause, form_clause = _parse_form_derivation_clause(text, atoms)
    if owns_form_clause:
        return (
            _render_form_derivation_clause(form_clause)
            if form_clause is not None
            else None
        )

    translated: list[str] = []
    position = 0
    matched_rule = False
    matched_governing_rule = False
    rendered_atom = False
    expects_operand = False
    term_context = False
    previous_token_was_marker = False
    previous_rule_was_connector = False
    operand_completed = False
    pending_governor = False
    while position < len(text):
        marker = _MARKER_RE.match(text, position)
        if marker:
            if previous_token_was_marker:
                return None
            atom = atoms[int(marker.group(1))]
            if atom.requires_companion and not _has_complete_companion(
                text, marker, atoms
            ):
                return None
            if (
                expects_operand
                and not atom.requires_companion
                and not atom.can_complete_operand
            ):
                return None
            if not term_context:
                remainder = text[marker.end() :].lstrip()
                if position != 0 or atom.standalone is None or not remainder.startswith((",", ";")):
                    return None
                translated.append(atom.standalone)
                matched_rule = True
                matched_governing_rule = True
                term_context = True
                operand_completed = True
            else:
                translated.append(atom.text)
            rendered_atom = True
            expects_operand = False
            previous_token_was_marker = True
            previous_rule_was_connector = False
            operand_completed = True
            pending_governor = False
            position = marker.end()
            continue

        for source, target in _TEXT_RULES:
            if _matches_rule(text, position, source):
                if pending_governor:
                    return None
                if source in _CONNECTOR_RULES and (
                    not term_context
                    or not operand_completed
                    or previous_rule_was_connector
                ):
                    return None
                translated.append(target)
                position += len(source)
                matched_rule = True
                previous_token_was_marker = False
                if source in _CONNECTOR_RULES:
                    expects_operand = True
                    previous_rule_was_connector = True
                elif source not in _NON_GOVERNING_RULES:
                    term_context = True
                    expects_operand = True
                    matched_governing_rule = True
                    previous_rule_was_connector = False
                    operand_completed = False
                    pending_governor = True
                break
        else:
            safe_text = _SAFE_TEXT_RE.match(text, position)
            if not safe_text:
                return None
            safe_value = safe_text.group(0)
            if pending_governor and any(
                punctuation in safe_value for punctuation in ",;:.?!"
            ):
                return None
            translated.append(safe_value)
            previous_token_was_marker = False
            if term_context and _NUMBER_OPERAND_RE.fullmatch(safe_value):
                rendered_atom = True
                operand_completed = True
                expects_operand = False
                pending_governor = False
            if expects_operand and any(
                punctuation in safe_value
                for punctuation in ";:.?!"
            ):
                return None
            if "," in safe_value and term_context:
                expects_operand = True
            if any(
                punctuation in safe_value
                for punctuation in ";:.?!"
            ):
                term_context = False
                expects_operand = False
                operand_completed = False
            position = safe_text.end()

    bare_statement = text.rstrip(".!?").strip()
    if (
        not matched_rule
        or expects_operand
        or pending_governor
        or (matched_governing_rule and not rendered_atom)
        or (
            not matched_governing_rule
            and not rendered_atom
            and bare_statement not in _STANDALONE_TEXT_RULES
        )
    ):
        return None
    return _finalise_statement("".join(translated))


def _translate_protected_text(text: str, atoms: list[_Atom]) -> str | None:
    """Translate every sentence and line without losing atom relations."""

    if re.search(r"[.!?][a-z]", text):
        return None
    statements = [
        statement
        for statement in re.split(
            f"(?<=[.!?])(?:\\s+|(?={_MARKER_START}|[A-Z]))|\\n+", text
        )
        if statement.strip()
    ]
    translated: list[str] = []
    for statement in statements:
        result = _translate_statement(statement, atoms)
        if result is None:
            return None
        translated.append(result)
    combined = " ".join(translated)
    if _BAD_PUNCTUATION_RE.search(combined):
        return None
    return combined or None


def translate_etymology(
    section: str,
    *,
    source: str = "en",
    target: str = "mg",
    translate_glosses: bool = False,
) -> str | None:
    """Translate one fully supported etymology section into Malagasy.

    Lexical terms and their wiki markup remain opaque. ``None`` is returned for
    unsupported language pairs, malformed markup, or unrecognised prose so a
    caller can retain its source fallback without publishing a partial result.
    """

    if source != "en" or target != "mg" or not isinstance(section, str):
        return None
    if len(section) > _MAX_SECTION_LENGTH:
        return None
    section = section.strip()
    if (
        not section
        or "\n=" in section
        or section.startswith(("=", "*", "#"))
    ):
        return None
    try:
        protected = _protect_wikitext(section)
        if protected is None:
            return None
        translated = _translate_protected_text(*protected)
        if translated is not None and translate_glosses:
            return _translate_glosses_in_etymology(translated)
        return translated
    except (OverflowError, RecursionError, ValueError):
        return None


def translate_etymologies(
    sections: Sequence[str],
    *,
    source: str = "en",
    target: str = "mg",
    translate_glosses: bool = False,
) -> list[str] | None:
    """Translate etymology sections, failing closed if any section is unsafe."""

    if source != "en" or target != "mg" or isinstance(sections, (str, bytes)):
        return None
    if len(sections) > _MAX_SECTIONS:
        return None
    translated: list[str] = []
    total_length = 0
    for section in sections:
        if not isinstance(section, str):
            return None
        total_length += len(section)
        if total_length > _MAX_BATCH_LENGTH:
            return None
        result = translate_etymology(
            section,
            source=source,
            target=target,
            translate_glosses=translate_glosses,
        )
        if result is None:
            return None
        translated.append(result)
    return translated or None


__all__ = ["translate_etymologies", "translate_etymology"]
