import re
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Iterator, List, Required, TypedDict

import mwparserfromhell
from mwparserfromhell.wikicode import Wikicode

from api.importer.wiktionary import (
    SubsectionImporter as BaseSubsectionImporter,
    WiktionaryAdditionalDataImporter,
)
from api.importer.wiktionary import use_wiktionary
from api.model.word import Translation
from api.parsers.etymology.en import render_template as render_etym_template
from conf.entryprocessor.languagecodes.en import LANGUAGE_CODES, LANGUAGE_NAMES

part_of_speech_translation = {
    "Verb": "mat",
    "Adjective": "mpam",
    "Conjunction": "mpampitohy",
    "Determiner": "mpam",
    "Idiom": "fomba fiteny",
    "Phrase": "fomba fiteny",
    "Proverb": "ohabolana",
    "Number": "isa",
    "Noun": "ana",
    "Adjectival noun": "mpam",
    "Particle": "kianteny",
    "Adverb": "tamb",
    "Root": "fototeny",
    "Numeral": "isa",
    "Pronoun": "solo-ana",
    "Preposition": "mp.ank-teny",
    "Contraction": "fanafohezana",
    "Letter": "litera",
    "Proper noun": "ana-pr",
    "Prefix": "tovona",
    "Romanization": "rômanizasiona",
    "Suffix": "tovana",
    "Symbol": "eva",
    "Participle": "ova-mat",
    "Interjection": "tenim-piontanana",
    "Infix": "tsofoka",
}


_HEADING_RE = re.compile(
    r"^(?P<equals>={2,6})\s*(?P<title>.*?)\s*(?P=equals)\s*$"
)
_NUMBERED_HEADING_RE = re.compile(r"\s+\d+(?:\.\d+)*$")
_INLINE_MODIFIER_RE = re.compile(r"<[^<>]*>")


@dataclass
class _WikicodeParseSession:
    """Canonical parses and derived values for one extraction operation."""

    wikicode_by_source: dict[str, Wikicode] = field(default_factory=dict)
    pronunciation_pos_by_line: dict[str, frozenset[str]] = field(
        default_factory=dict
    )


_PARSE_SESSION: ContextVar[_WikicodeParseSession | None] = ContextVar(
    "en_wiktionary_parse_session", default=None
)


@contextmanager
def wikicode_parse_session() -> Iterator[None]:
    """Share exact-source parses for one possibly nested extraction operation."""

    if _PARSE_SESSION.get() is not None:
        yield
        return

    token = _PARSE_SESSION.set(_WikicodeParseSession())
    try:
        yield
    finally:
        _PARSE_SESSION.reset(token)


def _parse_wikicode(source: str) -> Wikicode:
    """Return the operation's canonical read-only parse for exact ``source``."""

    session = _PARSE_SESSION.get()
    if session is None:
        return mwparserfromhell.parse(source)
    if source not in session.wikicode_by_source:
        session.wikicode_by_source[source] = mwparserfromhell.parse(source)
    return session.wikicode_by_source[source]


@dataclass(frozen=True)
class _WikiSection:
    """A heading and the text directly owned by that heading."""

    title: str
    level: int
    ancestors: tuple[tuple[int, str], ...]
    content: str
    part_of_speech: str | None
    branch_parts_of_speech: frozenset[str]


@dataclass
class _SectionBuilder:
    """Mutable state used only while constructing immutable sections."""

    title: str
    level: int
    ancestor_indexes: tuple[int, ...]
    lines: list[str] = field(default_factory=list)


class DescendantNode(TypedDict, total=False):
    """Preview-only recursive descendant data."""

    lang_code: Required[str]
    lang: Required[str]
    word: str
    roman: str
    tags: list[str]
    raw_tags: list[str]
    descendants: list["DescendantNode"]
    ruby: list[tuple[str, str]]
    sense: str


def _normalize_heading(title: str) -> str:
    """Normalize a heading for case-insensitive title matching."""

    title = re.sub(r"\s+", " ", title).strip()
    return _NUMBERED_HEADING_RE.sub("", title).casefold()


_POS_BY_HEADING = {
    _normalize_heading(title): code
    for title, code in part_of_speech_translation.items()
}
UNMAPPED_POS_HEADINGS = {
    "abbreviation",
    "acronym",
    "adjectival",
    "adjectival verb",
    "adjectives",
    "adjectuve",
    "adnominal",
    "adverbial phrase",
    "adverbs",
    "adjective suffix",
    "affix",
    "ambiposition",
    "article",
    "character",
    "circumfix",
    "circumposition",
    "classifier",
    "clipping",
    "clitic",
    "combining form",
    "comparative",
    "converb",
    "counter",
    "dependent noun",
    "definitions",
    "diacritical mark",
    "enclitic",
    "enclitic particle",
    "gerund",
    "han character",
    "han characters",
    "hanja",
    "hanzi",
    "ideophone",
    "infinitive",
    "initialism",
    "intransitive verb",
    "instransitive verb",
    "interfix",
    "interrogative pronoun",
    "kanji",
    "ligature",
    "nominal nuclear clause",
    "noum",
    "nouɲ",
    "noun form",
    "ordinal number",
    "past participle",
    "perfect expression",
    "perfect participle",
    "perfection expression",
    "personal pronoun",
    "phrases",
    "possessive determiner",
    "possessive pronoun",
    "postposition",
    "prepositional phrase",
    "prepositional expressions",
    "prepositional pronoun",
    "prepositions",
    "preverb",
    "present participle",
    "proper oun",
    "proposition",
    "punctuation",
    "punctuation mark",
    "relative",
    "suffix form",
    "syllable",
    "transitive verb",
    "verb form",
    "verbal noun",
    "verbs",
    "νoun",
}
_POS_OWNED_SECTION_HEADINGS = {
    "abbreviations",
    "ambiguous synonyms",
    "antonyms",
    "archetypes",
    "classes",
    "class",
    "cohyponyms",
    "comeronyms",
    "compounds",
    "coordinate term",
    "coordinate terms",
    "demonyms",
    "derived",
    "derived terms",
    "extensions",
    "holonyms",
    "hypernym",
    "hypernyms",
    "hyperonyms",
    "hyponyms",
    "idiomatic synonyms",
    "idioms",
    "idioms/phrases",
    "instances",
    "intances",
    "meronyms",
    "metonyms",
    "near antonyms",
    "near synonyms",
    "nouns",
    "proverbs",
    "proper nouns",
    "pseudo-synonyms",
    "related",
    "related characters",
    "related terms",
    "related words",
    "similes",
    "specific multiples",
    "synonyms",
    "troponyms",
    "variance",
    "various",
}


def _heading_part_of_speech(title: str) -> str | None:
    """Map a POS heading, using an empty string for known unsupported POSes."""

    normalized_title = _normalize_heading(title)
    if code := _POS_BY_HEADING.get(normalized_title):
        return code
    return "" if normalized_title in UNMAPPED_POS_HEADINGS else None


@lru_cache(maxsize=1)
def _parse_sections(wikipage: str) -> tuple[_WikiSection, ...]:
    """Parse exact MediaWiki headings and retain their ancestry."""

    builders: list[_SectionBuilder] = []
    stack: list[int] = []
    current_index: int | None = None

    for line in wikipage.splitlines():
        heading_match = _HEADING_RE.fullmatch(line)
        if heading_match is None:
            if current_index is not None:
                builders[current_index].lines.append(line)
            continue

        level = len(heading_match.group("equals"))
        while stack and builders[stack[-1]].level >= level:
            stack.pop()

        current_index = len(builders)
        builders.append(
            _SectionBuilder(
                title=heading_match.group("title").strip(),
                level=level,
                ancestor_indexes=tuple(stack),
            )
        )
        stack.append(current_index)

    branch_by_section: dict[int, int | None] = {}
    language_by_section: dict[int, int | None] = {}
    branch_parts_of_speech: dict[int, set[str]] = {}
    for index, builder in enumerate(builders):
        owner_indexes = (*builder.ancestor_indexes, index)
        language_by_section[index] = next(
            (
                owner_index
                for owner_index in owner_indexes
                if builders[owner_index].level == 2
            ),
            None,
        )
        branch_id = next(
            (
                owner_index
                for owner_index in reversed(owner_indexes)
                if _normalize_heading(builders[owner_index].title)
                in {"etymology", "glyph origin"}
            ),
            None,
        )
        branch_by_section[index] = branch_id
        own_pos = _heading_part_of_speech(builder.title)
        if branch_id is not None and own_pos is not None:
            branch_parts_of_speech.setdefault(branch_id, set()).add(own_pos)

    active_pos_by_scope: dict[tuple[int | None, int | None], str] = {}
    effective_pos_by_section: dict[int, str | None] = {}
    sections: list[_WikiSection] = []
    for index, builder in enumerate(builders):
        owner_indexes = (*builder.ancestor_indexes, index)
        structural_pos = next(
            (
                pos
                for owner_index in reversed(owner_indexes)
                if (
                    pos := _heading_part_of_speech(
                        builders[owner_index].title
                    )
                )
                is not None
            ),
            None,
        )
        scope = (language_by_section[index], branch_by_section[index])
        own_pos = _heading_part_of_speech(builder.title)
        if own_pos is not None:
            active_pos_by_scope[scope] = own_pos
        elif structural_pos is None:
            structural_pos = next(
                (
                    effective_pos_by_section[owner_index]
                    for owner_index in reversed(builder.ancestor_indexes)
                    if effective_pos_by_section.get(owner_index) is not None
                ),
                None,
            )
            if (
                structural_pos is None
                and _normalize_heading(builder.title)
                in _POS_OWNED_SECTION_HEADINGS
            ):
                structural_pos = active_pos_by_scope.get(scope)

        effective_pos_by_section[index] = structural_pos

        branch_id = branch_by_section[index]
        sections.append(
            _WikiSection(
                title=builder.title,
                level=builder.level,
                ancestors=tuple(
                    (builders[owner_index].level, builders[owner_index].title)
                    for owner_index in builder.ancestor_indexes
                ),
                content="\n".join(builder.lines).strip("\n"),
                part_of_speech=structural_pos,
                branch_parts_of_speech=frozenset(
                    branch_parts_of_speech.get(branch_id, set())
                ),
            )
        )

    return tuple(sections)


def _section_language(section: _WikiSection) -> str | None:
    """Return the L2 language heading that owns ``section``."""

    headings = (*section.ancestors, (section.level, section.title))
    return next((title for level, title in headings if level == 2), None)


def _section_part_of_speech(section: _WikiSection) -> str | None:
    """Return Botjagwar's POS code for the closest owning POS heading."""

    return section.part_of_speech


def _belongs_to_language(section: _WikiSection, language: str) -> bool:
    """Return whether ``section`` belongs to the requested language code."""

    language_title = _section_language(section)
    return language_title is None or LANGUAGE_NAMES.get(language_title) == language


def _belongs_to_part_of_speech(
    section: _WikiSection, part_of_speech: str | None
) -> bool:
    """Return whether a global or POS-owned section applies to an entry."""

    section_pos = _section_part_of_speech(section)
    if part_of_speech is None:
        return True
    if section_pos is not None:
        return section_pos == part_of_speech
    if section.branch_parts_of_speech:
        return part_of_speech in section.branch_parts_of_speech
    return True


def _ordered_unique(values: Iterable[str]) -> list[str]:
    """Deduplicate nonempty strings while retaining source order."""

    return list(dict.fromkeys(value for value in values if value))


def _template_name(template: mwparserfromhell.nodes.Template) -> str:
    """Return a normalized template name."""

    return re.sub(r"\s+", " ", str(template.name).replace("_", " ")).strip().casefold()


def _positional_parameters(
    template: mwparserfromhell.nodes.Template,
) -> list[tuple[int, str]]:
    """Return numeric template parameters sorted by their position."""

    parameters: dict[int, str] = {}
    for parameter in template.params:
        name = str(parameter.name).strip()
        if name.isdigit():
            parameters[int(name)] = str(parameter.value).strip()
    return sorted(parameters.items())


def _clean_term(value: str) -> str:
    """Normalize a directly encoded lexical target."""

    value = _INLINE_MODIFIER_RE.sub("", value).strip()
    if not value or value in {"-", "—", "?"}:
        return ""
    value = _parse_wikicode(value).strip_code().strip()
    value = re.sub(r"\s+", " ", value)
    value = value.split("#", 1)[0].strip(" ,;:")
    if not value or value.casefold().startswith(("category:", "thesaurus:")):
        return ""
    return value


def _clean_atom(value: str) -> str:
    """Normalize a non-wikitext pronunciation or metadata value."""

    return re.sub(r"\s+", " ", _INLINE_MODIFIER_RE.sub("", value)).strip()


def _split_plain_values(value: str) -> list[str]:
    """Split a comma- or semicolon-delimited pronunciation value."""

    return [part.strip() for part in re.split(r"\s*[,;]\s*", value) if part.strip()]


def _pronunciation_line_parts_of_speech(line: str) -> frozenset[str]:
    """Return direct POS labels attached to a pronunciation line."""

    session = _PARSE_SESSION.get()
    if session is not None and line in session.pronunciation_pos_by_line:
        return session.pronunciation_pos_by_line[line]

    parts_of_speech: set[str] = set()
    plain_line = re.sub(r"^[*#:;]+\s*", "", line)
    if ":" in plain_line:
        label_text = plain_line.split(":", 1)[0].casefold()
        for label in re.split(r"\s*(?:,|/|\band\b)\s*", label_text):
            if code := _POS_BY_HEADING.get(_normalize_heading(label)):
                parts_of_speech.add(code)

    qualifier_templates = {
        "a",
        "accent",
        "i",
        "label",
        "lb",
        "lbl",
        "q",
        "qual",
        "qualifier",
        "sense",
    }
    for template in _parse_wikicode(line).filter_templates(recursive=True):
        if _template_name(template) not in qualifier_templates:
            continue
        for _, value in _positional_parameters(template):
            if code := _POS_BY_HEADING.get(_normalize_heading(value)):
                parts_of_speech.add(code)
    result = frozenset(parts_of_speech)
    if session is not None:
        session.pronunciation_pos_by_line[line] = result
    return result


def _filter_pronunciation_lines(
    section: str, part_of_speech: str | None
) -> str:
    """Remove pronunciation lines explicitly labelled for another POS."""

    if part_of_speech is None:
        return section
    return "\n".join(
        line
        for line in section.splitlines()
        if not (labels := _pronunciation_line_parts_of_speech(line))
        or part_of_speech in labels
    )


class SubsectionImporter(BaseSubsectionImporter):
    section_name = ""
    section_names: tuple[str, ...] = ()
    # Retained for compatibility; numbered headings are normalized automatically.
    numbered = False
    level = 3
    levels = frozenset({3, 4, 5, 6})

    def __init__(self, **params: object) -> None:
        super(SubsectionImporter, self).__init__(**params)

    def set_whole_section_name(self, section_name: str) -> None:
        self.section_name = section_name
        self.section_names = ()

    def _target_names(self) -> set[str]:
        """Return normalized accepted section names."""

        names = self.section_names or (self.section_name,)
        return {_normalize_heading(name) for name in names}

    def get_sections(
        self,
        wikipage: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> list[_WikiSection]:
        """Return every matching section in source order and requested scope."""

        target_names = self._target_names()
        return [
            section
            for section in _parse_sections(wikipage)
            if section.level in self.levels
            and _normalize_heading(section.title) in target_names
            and _belongs_to_language(section, language)
            and _belongs_to_part_of_speech(section, part_of_speech)
        ]

    def get_data(
        self,
        template_title: str | None,
        wikipage: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> list[str]:
        """Return nonempty direct bodies from every matching section."""

        del template_title
        return [
            section.content
            for section in self.get_sections(wikipage, language, part_of_speech)
            if section.content.strip()
        ]


@use_wiktionary("en")
class ListSubsectionImporter(SubsectionImporter):
    inline_template_names: tuple[str, ...] = ()

    _single_term_templates = frozenset(
        {"desc", "descendant", "desctree", "l", "link", "m", "mention"}
    )
    _multi_term_templates = frozenset(
        {
            "abbr",
            "abbreviations",
            "alt",
            "alti",
            "alter",
            "ant",
            "antonyms",
            "col",
            "comeronyms",
            "coordinate terms",
            "cot",
            "der",
            "derived",
            "holonyms",
            "holo",
            "hyper",
            "hypernyms",
            "hyp",
            "hyponyms",
            "impf",
            "imperfectives",
            "inline alt forms",
            "instances",
            "mero",
            "meronyms",
            "near-syn",
            "nearsyn",
            "par",
            "parasyn",
            "parasynonyms",
            "perfectives",
            "pf",
            "proverbs",
            "related",
            "syn",
            "syndiff",
            "synonyms",
            "synsee",
            "troponyms",
        }
    )

    @classmethod
    def _extract_template_terms(
        cls,
        template: mwparserfromhell.nodes.Template,
        language: str,
    ) -> list[str]:
        """Extract directly supplied terms from a lexical-list template."""

        name = _template_name(template)
        positional = _positional_parameters(template)
        named_language = (
            str(template.get("lang").value).strip()
            if template.has("lang")
            else ""
        )

        if name == "pedia":
            values = [positional[0][1]] if positional else []
        elif name.endswith("-l") and name not in cls._multi_term_templates:
            values = [positional[0][1]] if positional else []
        elif name in cls._single_term_templates:
            if named_language:
                if named_language != language:
                    return []
                values = [positional[0][1]] if positional else []
            else:
                if not positional or positional[0][1] != language:
                    return []
                values = [
                    value for index, value in positional if index == 2
                ]
        elif (
            name in cls._multi_term_templates
            or re.fullmatch(r"(?:col|der)\d+", name)
        ):
            if named_language:
                if named_language != language:
                    return []
                values = [value for _, value in positional]
            else:
                if not positional or positional[0][1] != language:
                    return []
                values = [value for index, value in positional if index > 1]
        else:
            return []

        return _ordered_unique(_clean_term(value) for value in values)

    @classmethod
    def _extract_links(
        cls, item: str, language: str, *, fallback: bool = True
    ) -> List[str]:
        """Extract lexical targets from templates, links, or plain list text."""

        words: list[str] = []
        wikicode = _parse_wikicode(item)
        for node in wikicode.nodes:
            if isinstance(node, mwparserfromhell.nodes.Template):
                words.extend(cls._extract_template_terms(node, language))
            elif isinstance(node, mwparserfromhell.nodes.Wikilink):
                words.append(_clean_term(str(node.title)))

        if not words and fallback:
            plain_item = re.sub(r"^[*#:;]+\s*", "", item).strip()
            plain_item = wikicode.strip_code().strip() or plain_item
            if plain_item and not plain_item.startswith(("|", "}}")):
                words.append(_clean_term(plain_item))

        return _ordered_unique(words)

    @staticmethod
    def _logical_lines(text: str) -> list[str]:
        """Join list templates that span physical source lines."""

        logical_lines: list[str] = []
        buffer: list[str] = []
        template_depth = 0
        for line in text.splitlines():
            if buffer:
                buffer.append(line)
                template_depth += line.count("{{") - line.count("}}")
                if template_depth <= 0:
                    logical_lines.append("\n".join(buffer))
                    buffer = []
                continue
            template_depth = line.count("{{") - line.count("}}")
            if template_depth > 0:
                buffer = [line]
            else:
                logical_lines.append(line)
        if buffer:
            logical_lines.append("\n".join(buffer))
        return logical_lines

    def get_data(
        self,
        template_title: str | None,
        content: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> List[str]:
        """Return ordered lexical targets from matching sections and templates."""

        del template_title
        target_names = self._target_names()
        inline_names = {
            _normalize_heading(name) for name in self.inline_template_names
        }
        retrieved: list[str] = []
        for section in _parse_sections(content):
            if not _belongs_to_language(section, language) or not (
                _belongs_to_part_of_speech(section, part_of_speech)
            ):
                continue

            if (
                section.level in self.levels
                and _normalize_heading(section.title) in target_names
            ):
                for line in self._logical_lines(section.content):
                    item = line.strip()
                    if not item or "[[Thesaurus:" in item:
                        continue
                    if item.startswith("|"):
                        item = item.lstrip("|").replace("}}", "")
                        item = item.split("#", 1)[0].strip()
                        if item:
                            retrieved.append(_clean_term(item))
                        continue
                    retrieved.extend(self._extract_links(item, language))

            if inline_names:
                for template in _parse_wikicode(section.content).filter_templates(
                    recursive=True
                ):
                    if _template_name(template) in inline_names:
                        retrieved.extend(
                            self._extract_template_terms(template, language)
                        )
        return _ordered_unique(retrieved)


class SynonymImporter(ListSubsectionImporter):
    data_type = "synonym"
    section_name = "Synonyms"
    section_names = (
        "Synonyms",
        "Ambiguous synonyms",
        "Near synonyms",
        "Pseudo-synonyms",
        "Idiomatic synonyms",
    )
    inline_template_names = (
        "syn",
        "synonyms",
        "synsee",
        "syndiff",
        "parasynonyms",
        "par",
        "parasyn",
        "nearsyn",
        "near-syn",
    )


@use_wiktionary("en")
class EtymologyImporter(SubsectionImporter):
    data_type = "etym/en"
    section_name = "Etymology"
    section_names = ("Etymology", "Glyph origin")


@use_wiktionary("en")
class ParsedEtymologyImporter(EtymologyImporter):
    """Parse etymology section and render templates to plain text."""

    data_type = "etym/en/parsed"

    def _render_template(
        self, template: mwparserfromhell.nodes.Template
    ) -> str:
        """Render supported etymology templates to wikitext."""
        return render_etym_template(template)

    def _parse_text(self, text: str) -> str:
        code = deepcopy(_parse_wikicode(text))
        for tag in code.filter_tags(matches=lambda node: node.tag == "ref"):
            code.remove(tag)

        for tpl in code.filter_templates():
            try:
                rendered = self._render_template(tpl)
                if rendered:
                    code.replace(tpl, rendered)
            except ValueError:
                # Preserve templates whose custom renderer cannot handle them.
                continue

        result = re.sub(r"\s+", " ", str(code)).strip()
        if result and not result.endswith((".", "?", "!")):
            result += "."

        return result

    def get_data(
        self,
        template_title: str | None,
        wikipage: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> List[str]:
        """Return parsed text for numbered and unnumbered etymologies."""

        sections = super().get_data(
            template_title, wikipage, language, part_of_speech
        )
        return _ordered_unique(
            parsed
            for section in sections
            if section.strip()
            and (parsed := self._parse_text(section))
        )


@use_wiktionary("en")
class ReferencesImporter(SubsectionImporter):
    data_type = "reference"
    section_name = "References"
    filter_list = [
        "<references",  # References defined elsewhere
        "[[category:",  # Category section caught
        "==",  # Section caught
        "{{c|",  # Categorisation templates
        "{{l|",  # List element templates
        "{{comcatlite|",  # Commons category
    ]

    def has_filtered_element(self, ref: str) -> bool:
        """Return whether a reference line is structural rather than content."""

        if ref.startswith("|"):
            return True

        return any(element in ref.lower() for element in self.filter_list)

    def get_data(
        self,
        template_title: str | None,
        wikipage: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> list[str]:
        """Return non-structural reference lines from all matching sections."""

        refs = super(ReferencesImporter, self).get_data(
            template_title, wikipage, language, part_of_speech
        )
        refs_to_return: list[str] = []
        returned_references = "\n".join(refs)
        for ref_line in returned_references.split("\n"):
            ref_line = ref_line.strip()
            if not ref_line:
                continue

            if not self.has_filtered_element(ref_line):
                if ref_line.startswith("* "):
                    refs_to_return.append(ref_line.lstrip("* "))
                else:
                    refs_to_return.append(ref_line)

        return _ordered_unique(refs_to_return)


class FurtherReadingImporter(ReferencesImporter):
    section_name = "Further reading"
    data_type = "further_reading"


class SeeAlsoImporter(ListSubsectionImporter):
    data_type = "see_also"
    section_name = "See also"


class AlternativeFormsImporter(ListSubsectionImporter):
    data_type = "alternative_form"
    section_name = "Alternative forms"
    inline_template_names = ("alti", "inline alt forms")


class AntonymImporter(ListSubsectionImporter):
    data_type = "antonym"
    section_name = "Antonyms"
    section_names = ("Antonyms", "Near antonyms")
    inline_template_names = ("ant", "antonyms")


class AntonymImporterL5(AntonymImporter):
    level = 5
    levels = frozenset({5})


class DerivedTermsImporter(ListSubsectionImporter):
    data_type = "derived"
    section_name = "Derived terms"
    section_names = (
        "Derived",
        "Derived terms",
        "Compounds",
        "Extensions",
        "Nouns",
        "Proper nouns",
    )


class DerivedTermsL5Importer(DerivedTermsImporter):
    level = 5
    levels = frozenset({5})


class RelatedTermsImporter(ListSubsectionImporter):
    data_type = "related"
    section_name = "Related terms"
    section_names = (
        "Related",
        "Related terms",
        "Related words",
        "Related characters",
        "Idioms",
        "Idioms/phrases",
        "Similes",
        "Variance",
        "Specific multiples",
        "Various",
        "Metonyms",
        "Demonyms",
        "Comeronyms",
        "Cohyponyms",
    )
    inline_template_names = (
        "alti",
        "inline alt forms",
        "comeronyms",
        "perfectives",
        "pf",
        "imperfectives",
        "impf",
    )


class HypernymImporter(ListSubsectionImporter):
    data_type = "hypernym"
    section_name = "Hypernyms"
    section_names = ("Hypernyms", "Hypernym", "Hyperonyms", "Classes", "Class")
    inline_template_names = ("hyper", "hypernyms")


class HyponymImporter(ListSubsectionImporter):
    data_type = "hyponym"
    section_name = "Hyponyms"
    inline_template_names = ("hyp", "hyponyms")


class HolonymImporter(ListSubsectionImporter):
    data_type = "holonym"
    section_name = "Holonyms"
    inline_template_names = ("holo", "holonyms")


class MeronymImporter(ListSubsectionImporter):
    data_type = "meronym"
    section_name = "Meronyms"
    inline_template_names = ("mero", "meronyms")


class CoordinateTermsImporter(ListSubsectionImporter):
    data_type = "coordinate_term"
    section_name = "Coordinate terms"
    section_names = ("Coordinate terms", "Coordinate term")
    inline_template_names = ("cot", "coordinate terms")


class TroponymImporter(ListSubsectionImporter):
    data_type = "troponym"
    section_name = "Troponyms"
    inline_template_names = ("troponyms",)


class InstanceImporter(ListSubsectionImporter):
    data_type = "instance"
    section_name = "Instances"
    section_names = ("Instances", "Intances", "Archetypes")
    inline_template_names = ("instances",)


class ProverbImporter(ListSubsectionImporter):
    data_type = "proverb"
    section_name = "Proverbs"
    inline_template_names = ("proverbs",)


class AbbreviationImporter(ListSubsectionImporter):
    data_type = "abbreviation"
    section_name = "Abbreviations"
    inline_template_names = ("abbr", "abbreviations")


class DescendantImporter(ListSubsectionImporter):
    data_type = "descendant"
    section_name = "Descendants"
    _modifier_re = re.compile(
        r"<(?P<name>[a-z][a-z0-9]*)(?::(?P<value>[^<>]*))?>"
    )
    _descendant_templates = frozenset(
        {"desc", "descendant", "descendants tree", "desctree"}
    )
    _tree_single_term_templates = frozenset(
        {
            "l",
            "link",
            "m",
            "mention",
        }
    )
    _relation_parameters = (
        ("bor", "borrowed"),
        ("lbor", "learned borrowing"),
        ("slb", "semi-learned borrowing"),
        ("obor", "orthographic borrowing"),
        ("clq", "calque"),
        ("pclq", "partial calque"),
        ("sml", "semantic loan"),
        ("translit", "transliteration"),
        ("inh", "inherited"),
        ("der", "reshaped by analogy or addition of morphemes"),
        ("unc", "uncertain"),
    )
    _normalized_tags = frozenset(
        {
            "archaic",
            "colloquial",
            "dated",
            "dialectal",
            "f",
            "formal",
            "informal",
            "m",
            "n",
            "nonstandard",
            "obsolete",
            "plural",
            "rare",
            "singular",
            "slang",
            "vulgar",
        }
    )
    _language_name_overrides = {"zh": "Chinese"}
    _language_code_overrides = {"Chinese": "zh"}
    _max_language_code_length = 64
    _max_language_name_length = 128
    _max_metadata_length = 512
    _max_labels_per_node = 16
    _max_term_length = 512
    _max_term_source_length = 4_096
    _max_tree_depth = 32
    _max_tree_nodes = 2_000

    @classmethod
    def _extract_template_terms(
        cls,
        template: mwparserfromhell.nodes.Template,
        language: str,
    ) -> list[str]:
        """Extract descendant terms regardless of the descendant language."""

        name = _template_name(template)
        if name in cls._descendant_templates | cls._tree_single_term_templates:
            positional = _positional_parameters(template)
            template_language = (
                str(template.get("lang").value).strip()
                if template.has("lang")
                else positional[0][1]
                if positional
                else language
            )
            return super()._extract_template_terms(template, template_language)
        return super()._extract_template_terms(template, language)

    @staticmethod
    def _parameter_values(
        template: mwparserfromhell.nodes.Template,
    ) -> dict[str, str]:
        """Index template parameters once using MediaWiki's last-value rule."""

        return {
            str(parameter.name).strip().casefold(): str(parameter.value).strip()
            for parameter in template.params
        }

    @classmethod
    def _parameter_value(
        cls,
        template: mwparserfromhell.nodes.Template,
        *names: str,
        parameter_values: dict[str, str] | None = None,
    ) -> str:
        """Return the last nonempty value for the first matching parameter name."""

        values = (
            parameter_values
            if parameter_values is not None
            else cls._parameter_values(template)
        )
        for name in names:
            if not name:
                continue
            value = values.get(name.casefold(), "")
            if value:
                return value[: cls._max_metadata_length]
        return ""

    @classmethod
    def _parameter_enabled(
        cls,
        template: mwparserfromhell.nodes.Template,
        name: str,
        parameter_values: dict[str, str] | None = None,
    ) -> bool:
        """Return whether a boolean template parameter is enabled."""

        value = cls._parameter_value(
            template, name, parameter_values=parameter_values
        )
        return bool(value) and value.casefold() not in {"0", "n", "no", "false"}

    @classmethod
    def _relation_tags(
        cls,
        template: mwparserfromhell.nodes.Template,
        term_number: int | None = None,
        parameter_values: dict[str, str] | None = None,
    ) -> list[str]:
        """Return relation flags directly encoded by a descendant template."""

        tags: list[str] = []
        for parameter, tag in cls._relation_parameters:
            names = [parameter]
            if term_number is not None:
                names.append(f"{parameter}{term_number}")
            if any(
                cls._parameter_enabled(
                    template, name, parameter_values=parameter_values
                )
                for name in names
            ):
                tags.append(tag)
        return tags

    @classmethod
    def _parameter_labels(
        cls,
        template: mwparserfromhell.nodes.Template,
        name: str,
        term_number: int,
        *,
        global_for_all: bool,
        parameter_values: dict[str, str] | None = None,
    ) -> list[str]:
        """Return global and term-specific labels for one metadata parameter."""

        names: list[str] = []
        if global_for_all or term_number == 1:
            names.append(name)
        names.append(f"{name}{term_number}")
        labels: list[str] = []
        for parameter_name in names:
            value = cls._parameter_value(
                template,
                parameter_name,
                parameter_values=parameter_values,
            )
            for label in value.split(","):
                clean_label = label.strip()
                if clean_label:
                    labels.append(clean_label[: cls._max_metadata_length])
                if len(labels) >= cls._max_labels_per_node:
                    break
            if len(labels) >= cls._max_labels_per_node:
                break
        return list(dict.fromkeys(labels))

    @classmethod
    def _attach_labels(cls, node: DescendantNode, labels: Iterable[str]) -> None:
        """Classify known labels while retaining unknown qualifiers verbatim."""

        tags: list[str] = []
        raw_tags: list[str] = []
        for label_index, label in enumerate(labels):
            if label_index >= cls._max_labels_per_node:
                break
            clean_label = _parse_wikicode(label).strip_code().strip()
            if not clean_label:
                continue
            clean_label = clean_label[: cls._max_metadata_length]
            if clean_label.casefold() in cls._normalized_tags:
                tags.append(clean_label)
            else:
                raw_tags.append(clean_label)
        if tags:
            node["tags"] = list(dict.fromkeys([*node.get("tags", []), *tags]))
        if raw_tags:
            node["raw_tags"] = list(
                dict.fromkeys([*node.get("raw_tags", []), *raw_tags])
            )

    @staticmethod
    def _language_node(lang_code: str) -> DescendantNode:
        """Create the mandatory language fields for a descendant node."""

        normalized_code = (lang_code or "unknown")[
            : DescendantImporter._max_language_code_length
        ]
        return {
            "lang_code": normalized_code,
            "lang": DescendantImporter._language_name_overrides.get(
                normalized_code, LANGUAGE_CODES.get(normalized_code, "unknown")
            ),
        }

    @classmethod
    def _term_node(
        cls,
        raw_term: str,
        template: mwparserfromhell.nodes.Template,
        lang_code: str,
        term_number: int,
        display_term: str = "",
        fallback_roman: str = "",
        fallback_sense: str = "",
        parameter_values: dict[str, str] | None = None,
    ) -> DescendantNode | None:
        """Create one node from a direct descendant term and its modifiers."""

        if len(raw_term) > cls._max_term_source_length:
            return None
        modifiers: dict[str, list[str]] = {}
        for modifier_match in cls._modifier_re.finditer(raw_term):
            modifier_values = modifiers.setdefault(modifier_match.group("name"), [])
            if len(modifier_values) < cls._max_labels_per_node:
                modifier_values.append(
                    (modifier_match.group("value") or "1").strip()[
                        : cls._max_metadata_length
                    ]
                )

        term_without_modifiers = cls._modifier_re.sub("", raw_term).strip()
        if len(term_without_modifiers) > cls._max_term_length:
            return None
        numbered_suffix = str(term_number)
        alternate = (
            next(iter(modifiers.get("alt", [])), "")
            or display_term
            or cls._parameter_value(
                template,
                f"alt{numbered_suffix}",
                "alt" if term_number == 1 else "",
                parameter_values=parameter_values,
            )
        )
        displayed_term = alternate or term_without_modifiers
        if len(displayed_term) > cls._max_term_length:
            return None
        reconstructed = displayed_term.startswith("*")
        word = _clean_term(displayed_term)
        if reconstructed and word and not word.startswith("*"):
            word = "*" + word
        if not word or len(word) > cls._max_term_length:
            return None

        node = cls._language_node(lang_code)
        node["word"] = word

        roman = next(iter(modifiers.get("tr", [])), "") or cls._parameter_value(
            template,
            f"tr{numbered_suffix}",
            "tr" if term_number == 1 else "",
            "rom" if term_number == 1 else "",
            parameter_values=parameter_values,
        )
        if not roman:
            roman = fallback_roman
        if roman and roman != "-":
            clean_roman = _clean_atom(roman[: cls._max_metadata_length])
            if clean_roman:
                node["roman"] = clean_roman

        sense = (
            next(iter(modifiers.get("t", [])), "")
            or next(iter(modifiers.get("gloss", [])), "")
            or fallback_sense
            or cls._parameter_value(
                template,
                f"t{numbered_suffix}",
                f"gloss{numbered_suffix}",
                "t" if term_number == 1 else "",
                "gloss" if term_number == 1 else "",
                parameter_values=parameter_values,
            )
        )
        if sense:
            clean_sense = _parse_wikicode(
                sense[: cls._max_metadata_length]
            ).strip_code().strip()
            if clean_sense:
                node["sense"] = clean_sense

        relation_tags = cls._relation_tags(
            template, term_number, parameter_values=parameter_values
        )
        for modifier_name, relation_tag in cls._relation_parameters:
            if modifiers.get(modifier_name):
                relation_tags.append(relation_tag)
        if relation_tags:
            node["raw_tags"] = list(dict.fromkeys(relation_tags))

        labels: list[str] = []
        for modifier_name in ("q", "qq", "g", "l", "ll"):
            labels.extend(modifiers.get(modifier_name, []))
            labels.extend(
                cls._parameter_labels(
                    template,
                    modifier_name,
                    term_number,
                    global_for_all=modifier_name in {"q", "qq"},
                    parameter_values=parameter_values,
                )
            )
        cls._attach_labels(node, labels)
        return node

    @classmethod
    def _template_nodes(
        cls,
        template: mwparserfromhell.nodes.Template,
        max_nodes: int | None = None,
    ) -> list[DescendantNode]:
        """Extract directly supplied descendant nodes from one template."""

        node_limit = cls._max_tree_nodes if max_nodes is None else max_nodes
        if node_limit <= 0:
            return []
        name = _template_name(template)
        positional = _positional_parameters(template)
        positional_values = dict(positional)
        parameter_values = cls._parameter_values(template)
        named_language = cls._parameter_value(
            template, "lang", parameter_values=parameter_values
        )
        lang_code = "unknown"
        terms: list[tuple[int, str, str, str, str]] = []
        chinese_form_tags: list[str] = []

        if name in cls._descendant_templates:
            if named_language:
                lang_code = named_language
                first_term_index = 1
            elif positional:
                lang_code = positional[0][1] or "unknown"
                first_term_index = 2
            else:
                first_term_index = 1

            term_numbers = {
                index - first_term_index + 1
                for index in positional_values
                if index >= first_term_index
            }
            for parameter in template.params:
                parameter_match = re.fullmatch(
                    r"(?:alt|t|gloss|tr|q|qq|g|l|ll)(\d*)",
                    str(parameter.name).strip().casefold(),
                )
                if parameter_match is not None:
                    term_numbers.add(int(parameter_match.group(1) or "1"))
            terms = [
                (
                    term_number,
                    positional_values.get(first_term_index + term_number - 1, ""),
                    "",
                    "",
                    "",
                )
                for term_number in sorted(term_numbers)[:node_limit]
            ]
        elif name in cls._tree_single_term_templates:
            if named_language:
                lang_code = named_language
                term = positional_values.get(1, "")
                display_term = positional_values.get(2, "")
                fallback_sense = positional_values.get(3, "")
            elif positional:
                lang_code = positional[0][1] or "unknown"
                term = positional_values.get(2, "")
                display_term = positional_values.get(3, "")
                fallback_sense = positional_values.get(4, "")
            else:
                term = ""
                display_term = ""
                fallback_sense = ""
            terms = [(1, term, display_term, "", fallback_sense)]
        elif name == "ja-r":
            lang_code = "ja"
            terms = [
                (
                    1,
                    positional_values.get(1, ""),
                    "",
                    "",
                    positional_values.get(3, ""),
                )
            ]
        elif name in {"zh-l", "zh-m"}:
            lang_code = "zh"
            first_form = positional_values.get(1, "")
            second_value = positional_values.get(2, "")
            separate_forms = bool(
                first_form
                and second_value
                and re.search(r"[\u3400-\u9fff]", first_form)
                and re.search(r"[\u3400-\u9fff]", second_value)
                and positional_values.get(3)
            )
            if separate_forms:
                forms = [first_form, second_value]
                fallback_roman = positional_values.get(3, "")
                fallback_sense = positional_values.get(4, "")
                chinese_form_tags = ["Traditional-Chinese", "Simplified-Chinese"]
            else:
                forms = [
                    form.strip()
                    for form in re.split(r"[/／]", first_form)
                    if form.strip()
                ]
                if len(positional_values) >= 3:
                    fallback_roman = second_value
                    fallback_sense = positional_values.get(3, "")
                else:
                    fallback_roman = ""
                    fallback_sense = ""
                if len(forms) == 2:
                    chinese_form_tags = [
                        "Traditional-Chinese",
                        "Simplified-Chinese",
                    ]
            named_roman = cls._parameter_value(
                template, "tr", parameter_values=parameter_values
            )
            named_sense = cls._parameter_value(
                template, "t", "gloss", parameter_values=parameter_values
            )
            terms = [
                (
                    term_number,
                    form,
                    "",
                    named_roman or fallback_roman,
                    named_sense or fallback_sense,
                )
                for term_number, form in enumerate(forms, start=1)
            ]
        elif name.endswith("-l") and positional:
            lang_code = name.removesuffix("-l") or "unknown"
            terms = [(1, positional_values.get(1, ""), "", "", "")]
        else:
            return []

        nodes = [
            node
            for term_number, term, display_term, fallback_roman, fallback_sense in terms[
                :node_limit
            ]
            if (
                node := cls._term_node(
                    term,
                    template,
                    lang_code,
                    term_number,
                    display_term,
                    fallback_roman,
                    fallback_sense,
                    parameter_values,
                )
            )
            is not None
        ]
        for node, form_tag in zip(nodes, chinese_form_tags):
            node["tags"] = list(dict.fromkeys([*node.get("tags", []), form_tag]))
        if nodes:
            return nodes

        group_node = cls._language_node(lang_code)
        relation_tags = cls._relation_tags(
            template, parameter_values=parameter_values
        )
        if relation_tags:
            group_node["raw_tags"] = relation_tags
        return [group_node] if lang_code != "unknown" else []

    @staticmethod
    def _looks_like_group_name(text: str, *, has_children: bool) -> bool:
        """Recognize known languages and conventional capitalized family labels."""

        normalized_text = text.strip()
        if not normalized_text or not has_children:
            return normalized_text in LANGUAGE_NAMES
        words = normalized_text.replace("-", " ").split()
        return normalized_text in LANGUAGE_NAMES or (
            all(word[:1].isupper() for word in words)
            and (
                len(words) > 1
                or normalized_text.endswith(("an", "ic", "ish"))
            )
        )

    @classmethod
    def _item_nodes(
        cls,
        item: str,
        max_nodes: int | None = None,
        *,
        has_children: bool = False,
    ) -> list[DescendantNode]:
        """Extract all nodes represented by one descendant list item."""

        node_limit = cls._max_tree_nodes if max_nodes is None else max_nodes
        if node_limit <= 0:
            return []
        stripped_item = item.strip()
        label_match = re.match(r"^([^{}\[\]]+?):\s*(.*)$", stripped_item)
        lang_name = "unknown"
        lang_code = "unknown"
        plain_remainder = stripped_item
        if label_match is not None:
            lang_name = re.sub(
                r"^[→⇒>?]\s*", "", label_match.group(1)
            ).strip()[: cls._max_language_name_length]
            lang_code = cls._language_code_overrides.get(
                lang_name, LANGUAGE_NAMES.get(lang_name, "unknown")
            )
            plain_remainder = label_match.group(2).strip()

        nodes: list[DescendantNode] = []
        wikicode = _parse_wikicode(stripped_item)
        for child in wikicode.nodes:
            if isinstance(child, mwparserfromhell.nodes.Template):
                nodes.extend(
                    cls._template_nodes(child, max_nodes=node_limit - len(nodes))
                )
            elif isinstance(child, mwparserfromhell.nodes.Wikilink):
                raw_word = str(child.text or child.title)
                word = _clean_term(raw_word)
                if word and len(word) <= cls._max_term_length:
                    node = cls._language_node(lang_code)
                    node["lang"] = lang_name
                    node["word"] = word
                    nodes.append(node)
            if len(nodes) >= node_limit:
                break
        if nodes:
            return nodes

        if label_match is not None and not plain_remainder:
            return [{"lang": lang_name, "lang_code": lang_code}]
        if label_match is not None and plain_remainder:
            word = _clean_term(plain_remainder)
            if word:
                return [
                    {"lang": lang_name, "lang_code": lang_code, "word": word}
                ]

        plain_text = wikicode.strip_code().strip().rstrip(":").strip()
        if len(plain_text) > cls._max_term_length:
            return []
        if (
            len(plain_text) <= cls._max_language_name_length
            and cls._looks_like_group_name(
                plain_text, has_children=has_children
            )
        ):
            return [
                {
                    "lang": plain_text,
                    "lang_code": cls._language_code_overrides.get(
                        plain_text, LANGUAGE_NAMES.get(plain_text, "unknown")
                    ),
                }
            ]
        word = _clean_term(plain_text)
        if word:
            return [{"lang": "unknown", "lang_code": "unknown", "word": word}]
        return []

    @classmethod
    def _section_tree(
        cls, section: str, max_nodes: int | None = None
    ) -> list[DescendantNode]:
        """Build a bounded recursive forest from MediaWiki list ancestry."""

        roots: list[DescendantNode] = []
        nodes_by_marker: dict[str, list[DescendantNode]] = {}
        emitted_nodes = 0
        node_limit = cls._max_tree_nodes if max_nodes is None else max_nodes
        list_items: list[tuple[str, str]] = []
        for logical_line in cls._logical_lines(section):
            list_match = re.match(
                r"^\s*(?P<marker>[*#:;]+)\s*(?P<item>.*)$",
                logical_line,
                flags=re.DOTALL,
            )
            if list_match is None:
                continue
            list_items.append(
                (list_match.group("marker"), list_match.group("item"))
            )

        for item_index, (marker, item) in enumerate(list_items):
            if len(marker) > cls._max_tree_depth:
                continue
            next_marker = (
                list_items[item_index + 1][0]
                if item_index + 1 < len(list_items)
                else ""
            )
            nodes = cls._item_nodes(
                item,
                max_nodes=node_limit - emitted_nodes,
                has_children=len(next_marker) > len(marker)
                and next_marker.startswith(marker),
            )
            for previous_marker in [
                previous_marker
                for previous_marker in nodes_by_marker
                if len(previous_marker) >= len(marker)
                or not marker.startswith(previous_marker)
            ]:
                del nodes_by_marker[previous_marker]

            if not nodes:
                continue

            parent_marker = max(
                (
                    previous_marker
                    for previous_marker in nodes_by_marker
                    if marker.startswith(previous_marker)
                ),
                key=len,
                default=None,
            )
            attached_nodes: list[DescendantNode] = []
            if parent_marker is None:
                available_nodes = max(node_limit - emitted_nodes, 0)
                attached_nodes = nodes[:available_nodes]
                roots.extend(attached_nodes)
                emitted_nodes += len(attached_nodes)
            elif parent_nodes := nodes_by_marker[parent_marker]:
                for parent_node in parent_nodes:
                    available_nodes = max(node_limit - emitted_nodes, 0)
                    if not available_nodes:
                        break
                    child_nodes = deepcopy(nodes[:available_nodes])
                    parent_node.setdefault("descendants", []).extend(child_nodes)
                    attached_nodes.extend(child_nodes)
                    emitted_nodes += len(child_nodes)
            if attached_nodes:
                nodes_by_marker[marker] = attached_nodes
            if emitted_nodes >= node_limit:
                break
        return roots

    @staticmethod
    def _tree_node_count(nodes: Iterable[DescendantNode]) -> int:
        """Count recursive nodes iteratively to avoid recursion limits."""

        count = 0
        pending = list(nodes)
        while pending:
            node = pending.pop()
            count += 1
            pending.extend(node.get("descendants", []))
        return count

    def get_tree_data(
        self,
        template_title: str | None,
        wikipage: str,
        language: str,
        part_of_speech: str | None = None,
        max_nodes: int | None = None,
    ) -> list[DescendantNode]:
        """Return preview-only recursive descendants in source order."""

        del template_title
        descendants: list[DescendantNode] = []
        remaining_nodes = (
            self._max_tree_nodes
            if max_nodes is None
            else max(0, min(max_nodes, self._max_tree_nodes))
        )
        for section in self.get_sections(wikipage, language, part_of_speech):
            section_tree = self._section_tree(section.content, remaining_nodes)
            descendants.extend(section_tree)
            remaining_nodes -= self._tree_node_count(section_tree)
            if remaining_nodes <= 0:
                break
        return descendants


class PronunciationImporter(SubsectionImporter):
    data_type = "pronunciation"
    section_name = "Pronunciation"
    section_names = ("Pronunciation", "Production")

    def _section_data(
        self,
        wikipage: str,
        language: str,
        part_of_speech: str | None,
    ) -> list[str]:
        """Return applicable pronunciation bodies, including POS subsections."""

        sections = _parse_sections(wikipage)
        target_names = self._target_names()
        section_data: list[str] = []
        for index, section in enumerate(sections):
            if (
                section.level not in self.levels
                or _normalize_heading(section.title) not in target_names
                or not _belongs_to_language(section, language)
                or not _belongs_to_part_of_speech(section, part_of_speech)
            ):
                continue
            if section.content.strip():
                section_data.append(section.content)
            for descendant in sections[index + 1 :]:
                if descendant.level <= section.level:
                    break
                if (
                    _belongs_to_language(descendant, language)
                    and _belongs_to_part_of_speech(
                        descendant, part_of_speech
                    )
                    and descendant.content.strip()
                ):
                    section_data.append(descendant.content)
        return section_data

    def get_data(
        self,
        template_title: str | None,
        wikipage: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> list[str]:
        """Return every meaningful raw pronunciation line in source order."""

        del template_title
        parent_class_data = self._section_data(
            wikipage, language, part_of_speech
        )
        pronunciations: list[str] = []
        for section in parent_class_data:
            pending_lines: list[str] = []
            open_template_braces = 0
            for line in _filter_pronunciation_lines(
                section, part_of_speech
            ).splitlines():
                line = line.strip()
                if not line or line.casefold().startswith("[[category:"):
                    continue
                if not pending_lines:
                    line = re.sub(r"^\*+\s*", "", line)
                pending_lines.append(line)
                open_template_braces += line.count("{{") - line.count("}}")
                # A template spanning several lines stays one pronunciation.
                if open_template_braces > 0:
                    continue
                pronunciations.append("\n".join(pending_lines))
                pending_lines = []
                open_template_braces = 0
            if pending_lines:
                pronunciations.append("\n".join(pending_lines))
        return _ordered_unique(pronunciations)


class _PronunciationAtomImporter(PronunciationImporter):
    """Base importer for direct values in pronunciation templates."""

    template_names: frozenset[str] = frozenset()
    language_parameter = True

    def _template_values(
        self,
        template: mwparserfromhell.nodes.Template,
        language: str,
    ) -> list[str]:
        """Return values after an optional language argument."""

        positional = _positional_parameters(template)
        if template.has("lang"):
            if str(template.get("lang").value).strip() != language:
                return []
            return [value for _, value in positional]
        if positional and positional[0][1] == language:
            return [value for index, value in positional if index > 1]
        if self.language_parameter:
            return []
        return [value for _, value in positional]

    def _extract_from_section(self, section: str, language: str) -> list[str]:
        """Extract this atom from a raw pronunciation section."""

        values: list[str] = []
        for template in _parse_wikicode(section).filter_templates(recursive=True):
            if _template_name(template) in self.template_names:
                values.extend(self._template_values(template, language))
        return _ordered_unique(_clean_atom(value) for value in values)

    def get_data(
        self,
        template_title: str | None,
        wikipage: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> list[str]:
        """Return direct atom values from all matching pronunciation sections."""

        del template_title
        sections = self._section_data(
            wikipage, language, part_of_speech
        )
        return _ordered_unique(
            value
            for section in sections
            for value in self._extract_from_section(
                _filter_pronunciation_lines(section, part_of_speech),
                language,
            )
        )


class IPAImporter(_PronunciationAtomImporter):
    data_type = "ipa"
    template_names = frozenset({"ipa"})

    def _extract_from_section(self, section: str, language: str) -> list[str]:
        """Extract direct IPA arguments and untemplated IPA notation."""

        values = [
            value
            for value in super()._extract_from_section(section, language)
            if value not in {",", ";", "/"}
        ]
        wikicode = deepcopy(_parse_wikicode(section))
        for template in wikicode.filter_templates(recursive=False):
            wikicode.replace(template, "")
        for line in str(wikicode).splitlines():
            if "ipa" not in line.casefold():
                continue
            values.extend(
                match.group(0)
                for match in re.finditer(
                    r"(?:/[^/\n]+/|(?<!\[)\[(?!\[)[^\]\n]+\](?!\]))",
                    line,
                )
            )
        return _ordered_unique(values)


class AudioImporter(_PronunciationAtomImporter):
    data_type = "audio"
    template_names = frozenset({"audio", "audio-ipa", "audio-pron"})

    def _template_values(
        self,
        template: mwparserfromhell.nodes.Template,
        language: str,
    ) -> list[str]:
        """Return only the audio filename from a direct audio template."""

        values = super()._template_values(template, language)
        return values[:1]


class EnPRImporter(_PronunciationAtomImporter):
    data_type = "enpr"
    template_names = frozenset({"enpr"})
    language_parameter = False

    def _extract_from_section(self, section: str, language: str) -> list[str]:
        """Extract template and plain-text enPR values."""

        values = super()._extract_from_section(section, language)
        values.extend(
            match.group(1).strip()
            for match in re.finditer(r"(?im)\benPR\s*:\s*([^\n]+)", section)
        )
        return _ordered_unique(values)


class HyphenationImporter(_PronunciationAtomImporter):
    data_type = "hyphenation"
    template_names = frozenset({"hyph", "hyphenation"})

    def _extract_from_section(self, section: str, language: str) -> list[str]:
        """Join directly supplied syllable parts into flat hyphenations."""

        hyphenations: list[str] = []
        for template in _parse_wikicode(section).filter_templates(recursive=True):
            if _template_name(template) not in self.template_names:
                continue
            parts: list[str] = []
            for value in self._template_values(template, language):
                part = _clean_atom(value)
                if part:
                    parts.append(part)
                elif parts:
                    hyphenations.append("-".join(parts))
                    parts = []
            if parts:
                hyphenations.append("-".join(parts))
        for match in re.finditer(
            r"(?im)\b(?:Hyphenation|Syllabification)\s*:\s*([^\n]+)",
            section,
        ):
            hyphenations.extend(_split_plain_values(match.group(1)))
        return _ordered_unique(hyphenations)


class RhymeImporter(_PronunciationAtomImporter):
    data_type = "rhyme"
    template_names = frozenset({"rhyme", "rhymes", "rhymes-lite"})

    def _extract_from_section(self, section: str, language: str) -> list[str]:
        """Extract template and plain-text rhyme values."""

        values = super()._extract_from_section(section, language)
        for match in re.finditer(r"(?im)\bRhymes?\s*:\s*([^\n]+)", section):
            values.extend(_split_plain_values(match.group(1)))
        return _ordered_unique(values)


class HomophoneImporter(_PronunciationAtomImporter):
    data_type = "homophone"
    template_names = frozenset({"homophone", "homophones", "homophones-lite"})

    def _extract_from_section(self, section: str, language: str) -> list[str]:
        """Extract template and plain-text homophone targets."""

        values = super()._extract_from_section(section, language)
        for match in re.finditer(r"(?im)\bHomophones?\s*:\s*([^\n]+)", section):
            for item in _split_plain_values(match.group(1)):
                values.extend(
                    ListSubsectionImporter._extract_links(item, language)
                )
        return _ordered_unique(values)


class HeadwordImporter(WiktionaryAdditionalDataImporter):
    data_type = "headwords"
    section_name = None

    possible_headword_affixes = frozenset(
        {
            "adj",
            "adjective",
            "adv",
            "adverb",
            "article",
            "classifier",
            "conj",
            "conjunction",
            "counter",
            "det",
            "determiner",
            "infix",
            "interfix",
            "interj",
            "interjection",
            "letter",
            "noun",
            "num",
            "numeral",
            "part",
            "participle",
            "particle",
            "phrase",
            "postp",
            "postposition",
            "prefix",
            "prep",
            "preposition",
            "pronoun",
            "proper noun",
            "proper-noun",
            "root",
            "romanization",
            "suffix",
            "symbol",
            "verb",
        }
    )

    @classmethod
    def _is_headword_template(
        cls, template: mwparserfromhell.nodes.Template, language: str
    ) -> bool:
        """Return whether ``template`` is a direct headword template."""

        name = _template_name(template)
        if name == "head":
            positional = _positional_parameters(template)
            return bool(positional and positional[0][1] == language)
        prefix = f"{language}-"
        return name.startswith(prefix) and name[len(prefix) :] in cls.possible_headword_affixes

    def get_data(
        self,
        template_title: str | None,
        wikipage: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> list[str]:
        """Return raw generic and language-specific headword template lines."""

        del template_title
        sections = _parse_sections(wikipage)
        candidate_sections = [
            section
            for section in sections
            if _belongs_to_language(section, language)
            and _section_part_of_speech(section) is not None
            and _belongs_to_part_of_speech(section, part_of_speech)
        ]
        candidate_texts = (
            [section.content for section in candidate_sections]
            if sections
            else [wikipage]
        )

        template_lines: list[str] = []
        for candidate_text in candidate_texts:
            for template in _parse_wikicode(candidate_text).filter_templates(
                recursive=False
            ):
                if self._is_headword_template(template, language):
                    template_lines.append(str(template).strip())
        return _ordered_unique(template_lines)


class TranslationImporter(WiktionaryAdditionalDataImporter):
    level = 4
    data_type = "translations"
    section_name = "Translations"

    def get_data(
            self, wikipage: str, language: str, page_name: str = ""
    ) -> List[Translation]:
        """
        Warning: Will need reworking as this does not retrieve the specific definition that's  being translated in a
        given entry. If a definition is not specified, use the page name as the "definition".
        :return:
        """

        # Main regex to retrieve a given translation. Most entries use this format
        regex = r"\{\{t[\+]?\|([A-Za-z]{2,3})\|(.*?)\}\}"

        translations = {}
        entries = []
        content = re.sub("{{l/en\\|(.*)}}", "\\1 ", wikipage)  # remove {{l/en}}

        # Find the language section
        inside_translation_section = False
        for language in re.findall("[\n]?==[ ]?([A-Za-z]+)[ ]?==\n", content):
            last_part_of_speech = None
            content = content[content.find(f"=={language}=="):]
            lines = content.split("\n")
            for line in lines:
                for en_pos, mg_pos in part_of_speech_translation.items():
                    if f"==={en_pos}" in line:
                        last_part_of_speech = mg_pos

                if "{{trans-top" in line:
                    definition = line.strip("{{trans-top")
                    if definition[0] == "|":
                        definition = definition.strip("|")
                    elif not definition.strip("}}"):
                        definition = page_name

                    definition = definition.strip("}}")
                    inside_translation_section = True
                    continue

                if "{{trans-mid" in line:
                    continue

                if "{{trans-bottom" in line:
                    inside_translation_section = False

                if inside_translation_section and len(re.findall(regex, line)) != 0:
                    for language_code, translation in re.findall(regex, line):
                        translation = (
                            translation[: translation.find("|")]
                            if translation.find("|") != -1
                            else translation
                        )
                        if last_part_of_speech in translations:
                            translations[last_part_of_speech].append(
                                (language_code, translation, definition)
                            )
                        else:
                            translations[last_part_of_speech] = [
                                (language_code, translation, definition)
                            ]

            for pos, translation_list in translations.items():
                for translation_tuple in translation_list:
                    language, translation, definition = translation_tuple
                    entries.append(
                        Translation(
                            word=translation,
                            part_of_speech=pos,
                            language=language,
                            definition=definition,
                        )
                    )

        return entries


class TranscriptionImporter(WiktionaryAdditionalDataImporter):
    data_type = "transcription"
    section_name = None

    def get_data(
        self,
        template_title: str | None,
        wikipage: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> list[str]:
        """Return explicit ``tr=`` values from scoped headword templates."""

        template_lines: list[str] = []
        headword_importer = HeadwordImporter()
        headwords = headword_importer.get_data(
            template_title, wikipage, language, part_of_speech
        )
        for headword in headwords:
            for template in _parse_wikicode(headword).filter_templates(
                recursive=False
            ):
                if template.has("tr"):
                    template_lines.append(
                        str(template.get("tr").value).strip()
                    )

        return _ordered_unique(template_lines)


class _TemplateMetadataImporter(WiktionaryAdditionalDataImporter):
    """Base importer for explicit metadata in scoped template arguments."""

    page_title = ""

    def _extract_template(
        self,
        template: mwparserfromhell.nodes.Template,
        language: str,
    ) -> list[str]:
        """Return metadata represented by ``template``."""

        raise NotImplementedError

    def get_data(
        self,
        template_title: str | None,
        wikipage: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> list[str]:
        """Return explicit metadata from language- and POS-scoped content."""

        self.page_title = template_title or ""
        sections = _parse_sections(wikipage)
        candidate_texts = [
            section.content
            for section in sections
            if _belongs_to_language(section, language)
            and _belongs_to_part_of_speech(section, part_of_speech)
        ]
        if not sections:
            candidate_texts = [wikipage]

        values: list[str] = []
        for candidate_text in candidate_texts:
            for template in _parse_wikicode(candidate_text).filter_templates(
                recursive=True
            ):
                values.extend(self._extract_template(template, language))
        return _ordered_unique(values)


class WikipediaImporter(_TemplateMetadataImporter):
    data_type = "wikipedia"
    section_name = None
    template_names = frozenset(
        {
            "slim-wikipedia",
            "swp",
            "w",
            "wiki",
            "wikipedia",
            "wp",
            "wtorw",
        }
    )

    def _extract_template(
        self,
        template: mwparserfromhell.nodes.Template,
        language: str,
    ) -> list[str]:
        """Return an explicit Wikipedia target when present."""

        if _template_name(template) not in self.template_names:
            return []
        positional = _positional_parameters(template)
        if not positional:
            return [self.page_title] if self.page_title else []
        values = [value for _, value in positional]
        if len(values) > 1 and values[0] == language:
            values = values[1:]
        target = _parse_wikicode(values[0]).strip_code().strip()
        return [target] if target else []


class WikidataImporter(_TemplateMetadataImporter):
    data_type = "wikidata"
    section_name = None

    def _extract_template(
        self,
        template: mwparserfromhell.nodes.Template,
        language: str,
    ) -> list[str]:
        """Return explicit Wikidata item or lexeme identifiers."""

        del language
        if _template_name(template) != "wikidata":
            return []
        return [
            value
            for _, value in _positional_parameters(template)
            if re.fullmatch(r"(?:Q\d+|L\d+|Lexeme:L\d+)", value)
        ]


class LiteralMeaningImporter(_TemplateMetadataImporter):
    data_type = "literal_meaning"
    section_name = None

    def _extract_template(
        self,
        template: mwparserfromhell.nodes.Template,
        language: str,
    ) -> list[str]:
        """Return an explicit ``lit=`` template argument."""

        del language
        if _template_name(template) != "zh-forms" or not template.has("lit"):
            return []
        literal_meaning = _clean_term(str(template.get("lit").value))
        return [literal_meaning] if literal_meaning else []


all_importers = [
    FurtherReadingImporter,
    SeeAlsoImporter,
    AlternativeFormsImporter,
    AntonymImporter,
    DerivedTermsImporter,
    RelatedTermsImporter,
    HypernymImporter,
    HyponymImporter,
    HolonymImporter,
    MeronymImporter,
    CoordinateTermsImporter,
    TroponymImporter,
    InstanceImporter,
    ProverbImporter,
    AbbreviationImporter,
    DescendantImporter,
    PronunciationImporter,
    IPAImporter,
    AudioImporter,
    EnPRImporter,
    HyphenationImporter,
    RhymeImporter,
    HomophoneImporter,
    ReferencesImporter,
    EtymologyImporter,
    ParsedEtymologyImporter,
    SynonymImporter,
    HeadwordImporter,
    TranscriptionImporter,
    WikipediaImporter,
    WikidataImporter,
    LiteralMeaningImporter,
]
