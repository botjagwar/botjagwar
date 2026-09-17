import logging
import re
import threading
import unicodedata
from functools import lru_cache
from typing import ClassVar, FrozenSet, Optional

import mwparserfromhell
import requests

from api.config import BotjagwarConfig
from api.http_client import BULK_HTTP_TIMEOUT
from api.model.word import Entry
from conf.entryprocessor.languagecodes.en import LANGUAGE_CODES
from .base import PageRenderer


GENERATED_NLLB_NOUN_PREFIX_RE = re.compile(
    r"^-\s*ny\s+is\s+a(?:n|\[n\])?(?:\s+|$)", re.IGNORECASE
)
CYRILLIC_STRESS_MARKS = {"\N{COMBINING ACUTE ACCENT}", "\N{COMBINING GRAVE ACCENT}"}


def strip_generated_nllb_noun_prefix(definition: str) -> str:
    """Remove the known mixed-language noun prefix before publication."""

    return GENERATED_NLLB_NOUN_PREFIX_RE.sub("", definition).strip()


def _related_term_link(term: str, language: str) -> str:
    """Link diacritic spellings to the page title used for the language."""

    decomposed_term = unicodedata.normalize("NFD", term)
    if language == "la":
        target = "".join(
            character
            for character in decomposed_term
            if unicodedata.category(character) != "Mn"
        )
    elif language in {"ru", "uk"}:
        target = "".join(
            character
            for character in decomposed_term
            if character not in CYRILLIC_STRESS_MARKS
        )
    else:
        target = decomposed_term

    target = unicodedata.normalize("NFC", target)
    if target != term:
        return f"[[{target}|{term}]]"
    return f"[[{term}]]"


class MGWikiPageRendererError(Exception):
    pass


@lru_cache(maxsize=4)
def definition_link_index(
    pages_to_link: FrozenSet[str],
) -> dict[str, tuple[tuple[str, tuple[str, ...]], ...]]:
    """Index an immutable candidate set once, preferring longer phrases."""
    candidates_by_first_word: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    for target in pages_to_link:
        words = tuple(target.lower().split())
        if not words:
            continue
        candidates_by_first_word.setdefault(words[0], []).append((target, words))
    return {
        first_word: tuple(
            sorted(candidates, key=lambda candidate: (-len(candidate[1]), candidate[0]))
        )
        for first_word, candidates in candidates_by_first_word.items()
    }


def link_definition_segments(
    definition: str,
    pages_to_link: FrozenSet[str],
    current_word: str = "",
) -> list[tuple[str, Optional[str]]]:
    """Return plain and linked definition segments using longest phrase matches."""
    if "[[" in definition or "]]" in definition:
        return [(definition, None)]

    candidates_by_first_word = definition_link_index(pages_to_link)

    parts = re.split(r"(\s+)", definition)
    token_part_indexes = [
        part_index
        for part_index, part in enumerate(parts)
        if part and not part.isspace()
    ]
    linked_targets: set[str] = set()
    current_target = current_word.lower()
    segments: list[tuple[str, Optional[str]]] = []

    def append_segment(text: str, target: Optional[str] = None) -> None:
        if not text:
            return
        if target is None and segments and segments[-1][1] is None:
            segments[-1] = (segments[-1][0] + text, None)
        else:
            segments.append((text, target))

    token_index = 0
    part_index = 0
    while part_index < len(parts):
        if token_index >= len(token_part_indexes) or token_part_indexes[token_index] != part_index:
            append_segment(parts[part_index])
            part_index += 1
            continue

        first_word = parts[part_index].strip(",.;:")
        match: Optional[tuple[str, tuple[str, ...]]] = None
        for candidate in candidates_by_first_word.get(first_word.lower(), []):
            target, words = candidate
            normalised_target = target.lower()
            if (
                normalised_target == current_target
                or normalised_target in linked_targets
                or token_index + len(words) > len(token_part_indexes)
            ):
                continue
            actual_words = tuple(
                parts[token_part_indexes[token_index + offset]].strip(",.;:").lower()
                for offset in range(len(words))
            )
            if actual_words == words:
                match = candidate
                break

        if match is None:
            append_segment(parts[part_index])
            token_index += 1
            part_index += 1
            continue

        target, words = match
        last_part_index = token_part_indexes[token_index + len(words) - 1]
        last_word = parts[last_part_index].strip(",.;:")
        first_offset = parts[part_index].find(first_word)
        last_end = parts[last_part_index].rfind(last_word) + len(last_word)
        matched_text = "".join(parts[part_index : last_part_index + 1])
        link_end = len("".join(parts[part_index:last_part_index])) + last_end
        append_segment(parts[part_index][:first_offset])
        append_segment(matched_text[first_offset:link_end], target)
        append_segment(parts[last_part_index][last_end:])
        linked_targets.add(target.lower())
        token_index += len(words)
        part_index = last_part_index + 1

    return segments


def _sound_template_parameters(
    template: mwparserfromhell.nodes.Template,
) -> tuple[dict[str, str], dict[int, str]]:
    """Return last-value-wins named and positional sound parameters."""

    named: dict[str, str] = {}
    positional: dict[int, str] = {}
    for parameter in template.params:
        name = str(parameter.name).strip()
        value = str(parameter.value).strip()
        if name.isdigit():
            positional[int(name)] = value
        else:
            named[name.casefold()] = value
    return named, positional


def _has_unrepresented_sound_metadata(
    template_name: str, named: dict[str, str], positional: dict[int, str]
) -> bool:
    """Return whether normalized sound atoms would lose template semantics."""

    if named.keys() - {"lang"}:
        return True
    values = positional.values()
    if template_name == "ipa":
        return any(
            "<" in value or value.strip() in {",", ";", "/"} for value in values
        )
    return template_name in {"audio", "audio-ipa", "audio-pron"} and len(
        positional
    ) > 3


def _retained_sound_atoms(line: str, language: str) -> tuple[set[str], set[str]]:
    """Return normalized atoms whose metadata requires retaining the raw template."""

    retained_ipa: set[str] = set()
    retained_audio: set[str] = set()
    for template in mwparserfromhell.parse(line).filter_templates(recursive=False):
        template_name = str(template.name).strip().replace("_", " ").casefold()
        named, positional = _sound_template_parameters(template)
        if not _has_unrepresented_sound_metadata(template_name, named, positional):
            continue
        values = [value for _, value in sorted(positional.items())]
        if named.get("lang") == language:
            sound_values = values
        elif values and values[0] == language:
            sound_values = values[1:]
        else:
            continue
        if template_name == "ipa":
            retained_ipa.update(
                clean_value
                for value in sound_values
                if (clean_value := re.sub(r"<[^<>]*>", "", value).strip())
                not in {",", ";", "/"}
            )
        elif template_name in {"audio", "audio-ipa", "audio-pron"} and sound_values:
            retained_audio.add(sound_values[0])
    return retained_ipa, retained_audio


def strip_redundant_pronunciation_templates(
    line: str, *, has_ipa: bool, has_audio: bool
) -> str:
    """Remove represented sound templates while retaining their qualifiers."""

    wikicode = mwparserfromhell.parse(line)
    for template in wikicode.filter_templates(recursive=False):
        template_name = str(template.name).strip().replace("_", " ").casefold()
        named_parameters, positional_parameters = _sound_template_parameters(template)
        if has_ipa and template_name == "ipa":
            if _has_unrepresented_sound_metadata(
                template_name, named_parameters, positional_parameters
            ):
                continue
            wikicode.remove(template)
        elif has_audio and template_name in {"audio", "audio-ipa", "audio-pron"}:
            if _has_unrepresented_sound_metadata(
                template_name, named_parameters, positional_parameters
            ):
                continue
            description = positional_parameters.get(3, "")
            if description and description.casefold() not in {
                "audio",
                "audio clip",
                "pronunciation",
            }:
                wikicode.replace(template, f"({description})")
            else:
                wikicode.remove(template)
    retained = re.sub(r"[ \t]+", " ", str(wikicode)).strip()
    if re.fullmatch(r"[*#:;]?\s*(?:IPA|audio)\s*:?\s*", retained, re.IGNORECASE):
        return ""
    return retained


_LEVEL_2_SECTION_PATTERN = re.compile(r"^==(?P<title>[^=\n]+?(?:=[^=\n]+?)*)==(?=[ ]*==|$)")
_LEGACY_LANGUAGE_SECTION_PATTERN = re.compile(r"^\{\{=(?P<code>[^=]+?)=\}\}$")


def _level_2_section_titles(line: str) -> list:
    """Return the titles of every level-2 section header found on a line."""
    stripped_line = line.strip()
    titles = []
    while True:
        match = _LEVEL_2_SECTION_PATTERN.match(stripped_line)
        if match is None:
            return titles
        titles.append(match.group("title").strip())
        stripped_line = stripped_line[match.end():].strip()


def _is_language_section(section_title: str, language_section: str, language_names: set) -> bool:
    """Check whether a level-2 section title denotes the given language section.

    Matches the legacy ``{{=lang=}}`` form, the canonical language name in any
    of its word forms and any other language code sharing those names.
    """
    legacy_match = _LEGACY_LANGUAGE_SECTION_PATTERN.match(section_title)
    if legacy_match is not None:
        return legacy_match.group("code").strip() == language_section
    if section_title.lower() in language_names:
        return True
    return bool(_language_names_of(section_title) & language_names)


def _language_names_of(language_code: str) -> set:
    """Return the lowercase names a language section may use for a code."""
    language_name = LANGUAGE_CODES.get(language_code)
    if language_name is None:
        return set()
    return {
        language_name.lower(),
        language_name.lower().replace(" ", "_"),
        language_name.lower().replace(" ", "-"),
    }


class MGWikiPageRenderer(PageRenderer):

    _pages_to_link_cache: ClassVar[Optional[FrozenSet[str]]] = None
    _pages_to_link_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self):
        super(MGWikiPageRenderer, self).__init__()
        self.config = BotjagwarConfig()

    @property
    def pages_to_link(self) -> FrozenSet[str]:
        """Return the process-wide immutable set of linkable Malagasy pages."""
        cached = type(self)._pages_to_link_cache
        if cached is not None:
            return cached

        with type(self)._pages_to_link_lock:
            cached = type(self)._pages_to_link_cache
            if cached is None:
                try:
                    cached = frozenset(self.fetch_pages_to_link())
                except (
                    requests.RequestException,
                    MGWikiPageRendererError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    logging.getLogger(__name__).warning(
                        "Unable to load Malagasy pages for automatic links: %s", exc
                    )
                    cached = frozenset()
                type(self)._pages_to_link_cache = cached
        return cached

    def fetch_pages_to_link(self) -> set[str]:
        """Fetch linkable Malagasy words from PostgREST."""
        postgrest_url = self.config.get("postgrest_backend_address")
        url = f"http://{postgrest_url}/rpc/linkable_lexicon_headwords"

        pages = requests.get(
            url,
            timeout=BULK_HTTP_TIMEOUT,
        )
        if pages.status_code != 200:
            raise MGWikiPageRendererError(pages.status_code)
        words_to_link = {p["word"] for p in pages.json()}
        logging.getLogger(__name__).info(
            "Loaded %d Malagasy words for automatic links.", len(words_to_link)
        )
        return words_to_link

    def link_if_exists(self, definition: str, current_word: str = "") -> str:
        """Render the first longest match for each linkable target in a definition."""
        return "".join(
            text
            if target is None
            else f"[[{target}]]"
            if text == target
            else f"[[{target}|{text}]]"
            for text, target in link_definition_segments(
                definition,
                self.pages_to_link,
                current_word,
            )
        )

    def render(self, info: Entry, link=True) -> str:
        additional_note = ""
        if info.additional_data is not None and (
                        "origin_wiktionary_page_name" in info.additional_data
                        and "origin_wiktionary_edition" in info
                    ):
            additional_note = (
                " {{dikantenin'ny dikanteny|"
                + f"{info.additional_data['origin_wiktionary_page_name']}"
                f"|{info.additional_data['origin_wiktionary_edition']}" + "}}\n"
            )

        returned_string = self.render_head_section(info)
        returned_string += self.render_definitions(info, link) + additional_note
        # returned_string += self.render_inflection(info)
        returned_string += self.render_pronunciation(info)
        returned_string += self.render_synonyms(info)
        returned_string += self.render_antonyms(info)
        returned_string += self.render_related_terms(info)
        returned_string += self.render_further_reading(info)
        returned_string += self.render_references(info)

        return returned_string + "\n"

    def render_head_section(self, info):
        # Language
        returned_string = "\n=={{=" + f"{info.language}" + "=}}==\n"

        returned_string += self.render_etymology(info)

        # Part of speech
        returned_string += "\n{{-" + f"{info.part_of_speech}-|{info.language}" + "}}\n"

        # Pronunciation
        returned_string += "'''{{subst:BASEPAGENAME}}''' "

        # transcription (if any)
        if info.additional_data is not None and "transcription" in info.additional_data:
            transcriptions = ", ".join(info.additional_data["transcription"])
            returned_string += f"({transcriptions})"

        return returned_string

    def render_etymology(self, info):
        returned_string = ""
        additional_data = (
            info.additional_data
            if isinstance(info.additional_data, dict)
            else {}
        )
        if "etymology" not in additional_data:
            return returned_string
        etymology = additional_data["etymology"]
        returned_string += "\n{{-etim-}}\n"
        if not etymology:
            return returned_string + f": {{{{vang-etim|{info.language}}}}}\n"
        if isinstance(etymology, list):
            etymology = " ".join(etymology)
        returned_string += f":{etymology}"

        return returned_string

    def render_definitions(self, info, link: list):
        returned_string = ""
        definitions = []
        defn_list = []
        examples_by_definition = []
        raw_examples = (info.additional_data or {}).get("examples", [])
        examples_are_aligned = (
            isinstance(raw_examples, list)
            and len(raw_examples) == len(info.definitions)
        )
        definition_indexes = {}
        for index, definition in enumerate(info.definitions):
            definition = strip_generated_nllb_noun_prefix(definition)
            if not definition:
                continue
            if definition not in definition_indexes:
                definition_indexes[definition] = len(defn_list)
                defn_list.append(definition)
                examples_by_definition.append([])
            if examples_are_aligned and isinstance(raw_examples[index], list):
                target_index = definition_indexes[definition]
                examples_by_definition[target_index].extend(raw_examples[index])

        if link:
            trailing_characters_to_exclude_from_link = ",.;:"
            for d in defn_list:
                if "[[" in d or "]]" in d:
                    definitions.append(d)
                elif len(d.split()) == 1:
                    if d[-1] in trailing_characters_to_exclude_from_link:
                        for (
                            trailing_character_to_exclude_from_link
                        ) in trailing_characters_to_exclude_from_link:
                            if d.endswith(trailing_character_to_exclude_from_link):
                                temp_d = d.strip(".")
                                definitions.append(f"[[{temp_d.lower()}|{temp_d}]].")
                                break
                    else:
                        definitions.append(f"[[{d}]]")
                else:
                    current_word = info.entry if isinstance(getattr(info, "entry", ""), str) else ""
                    definition = self.link_if_exists(d, current_word)
                    definition = definition.replace(" - ", "-")
                    definitions.append(definition)

        else:
            definitions = [f"{d}" for d in defn_list]

        citation_sources = {}
        for citation in (info.additional_data or {}).get("citations", []) or []:
            if (
                isinstance(citation, dict)
                and citation.get("text")
                and citation.get("source")
            ):
                citation_sources.setdefault(citation["text"], citation["source"])

        for idx, defn in enumerate(definitions):
            returned_string += "\n# " + defn
            for example in dict.fromkeys(examples_by_definition[idx]):
                source = citation_sources.get(example)
                if source:
                    # Sourced quotations carry their full citation after the
                    # passage, separated by an en dash.
                    returned_string += (
                        "\n#* ''" + example + " \u2013 " + source + "''"
                    )
                else:
                    returned_string += "\n#* ''" + example + "''"

        return returned_string

    def render_inflection(self, info):
        returned_string = ""
        if "inflection" in info.additional_data:
            returned_string = "\n{{-bikan-teny-}}\n"
            returned_string += "\n".join(info.additional_data["inflection"]) + "\n"

        return returned_string

    def render_pronunciation(self, info):
        returned_string = ""
        header_added = False
        retained_ipa_atoms: set[str] = set()
        retained_audio_files: set[str] = set()

        # Generic pronunciation section
        if "pronunciation" in info.additional_data:
            raw_pronunciations = info.additional_data["pronunciation"]
            if not isinstance(raw_pronunciations, list):
                raw_pronunciations = [raw_pronunciations]
            for pronunciation in raw_pronunciations:
                retained_ipa, retained_audio = _retained_sound_atoms(
                    pronunciation, info.language
                )
                retained_ipa_atoms.update(retained_ipa)
                retained_audio_files.update(retained_audio)
            raw_pronunciations = [
                retained_pronunciation
                for pronunciation in raw_pronunciations
                if (
                    retained_pronunciation := strip_redundant_pronunciation_templates(
                        pronunciation,
                        has_ipa=bool(info.additional_data.get("ipa")),
                        has_audio=bool(info.additional_data.get("audio")),
                    )
                )
            ]
            if raw_pronunciations:
                if not header_added:
                    returned_string += "\n\n{{-fanononana-}}"
                    header_added = True
                for pron in raw_pronunciations:
                    returned_string += "\n* " + pron.strip("*").strip()

        # Pronunciation and/or Audio
        audio_pronunciations = list(
            dict.fromkeys(
                [
                    *info.additional_data.get("audio_pronunciations", []),
                    *info.additional_data.get("audio", []),
                ]
            )
        )
        audio_pronunciations = [
            audio
            for audio in audio_pronunciations
            if audio not in retained_audio_files
        ]
        if audio_pronunciations:
            if not header_added:
                returned_string += "\n\n{{-fanononana-}}"
                header_added = True
            for audio in audio_pronunciations:
                returned_string += (
                    "\n* " + "{{audio|" + f"{audio}" + "|" + f"{info.entry}" + "}}"
                )

        # IPA
        if "ipa" in info.additional_data:
            if not header_added:
                returned_string += "\n\n{{-fanononana-}}"
                header_added = True
            for ipa in info.additional_data["ipa"]:
                if ipa in retained_ipa_atoms:
                    continue
                returned_string += (
                    "\n* "
                    + "{{fanononana|"
                    + f"{ipa}"
                    + "|"
                    + f"{info.language}"
                    + "}}"
                )

        return returned_string

    def render_synonyms(self, info):
        returned_string = ""
        synonyms = list(
            dict.fromkeys(
                [
                    *info.additional_data.get("synonyms", []),
                    *info.additional_data.get("synonym", []),
                ]
            )
        )
        if synonyms:
            returned_string += "\n\n{{-dika-mitovy-}}"
            for synonym in synonyms:
                returned_string += "\n* [[" + synonym + "]]"

        return returned_string

    def render_antonyms(self, info) -> str:
        returned_string = ""
        antonyms = list(
            dict.fromkeys(
                [
                    *info.additional_data.get("antonyms", []),
                    *info.additional_data.get("antonym", []),
                ]
            )
        )
        if antonyms:
            returned_string += "\n\n{{-dika-mifanohitra-}}"
            for antonym in antonyms:
                returned_string += "\n* [[" + antonym + "]]"

        return returned_string

    def render_related_terms(self, info) -> str:
        returned_string = ""
        related_terms = list(
            dict.fromkeys(
                [
                    *info.additional_data.get("related_terms", []),
                    *info.additional_data.get("related", []),
                ]
            )
        )
        derived_terms = list(
            dict.fromkeys(
                [
                    *info.additional_data.get("derived_terms", []),
                    *info.additional_data.get("derived", []),
                ]
            )
        )
        if related_terms or derived_terms:
            returned_string += "\n\n{{-teny mifandraika-}}"
        for related_term in [*related_terms, *derived_terms]:
            returned_string += f"\n* {_related_term_link(related_term, info.language)}"

        return returned_string

    def render_section(self, info, section_header, attr_name):
        returned_string = ""
        if attr_name in info.additional_data:
            if section_header not in returned_string:
                returned_string += "\n\n" + section_header
            section_data = info.additional_data[attr_name]
            if isinstance(section_data, list):
                if len(section_data) > 1:
                    for ref in info.additional_data[attr_name]:
                        returned_string += "\n* " + ref
                elif len(section_data) == 1:
                    returned_string += "\n" + section_data[0]

        return returned_string

    def render_further_reading(self, info):
        return self.render_section(info, "{{-famakiana fanampiny-}}", "further_reading")

    def render_references(self, info) -> str:
        return "".join(
            self.render_section(info, "{{-tsiahy-}}", attr_name)
            for attr_name in [
                "references",
                "reference",
            ]
        )

    def delete_section(self, language_section, wiki_page):
        language_names = _language_names_of(language_section)
        section_begin = None
        section_end = None
        lines = wiki_page.split("\n")
        for line_no, line in enumerate(lines):
            if section_begin is None:
                for section_title in _level_2_section_titles(line):
                    if _is_language_section(section_title, language_section, language_names):
                        section_begin = line_no
                        break
                continue

            if _level_2_section_titles(line):
                section_end = line_no
                break

        if section_begin is None:
            return wiki_page

        if section_end is not None:
            to_delete = "\n".join(lines[section_begin:section_end])
        else:
            to_delete = "\n".join(lines[section_begin:])

        return wiki_page.replace(to_delete, "")
