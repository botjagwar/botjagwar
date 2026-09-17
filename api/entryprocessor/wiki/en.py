# coding: utf8
import re
import mwparserfromhell

from api.importer.wiktionary.en import (
    DescendantImporter,
    DescendantNode,
    UNMAPPED_POS_HEADINGS,
    TranslationImporter,
    all_importers,
    wikicode_parse_session,
)
from api.model.word import Entry
from api.parsers.en import TEMPLATE_TO_OBJECT, templates_parser
from api.parsers.inflection_template import ParserNotFoundError
from api.utils.citations import localize_citation_date

from api.translation_v2.functions.definitions.preprocessors import (
    refine_definition,
    drop_definitions_with_labels, drop_all_labels,
)

from conf.entryprocessor.languagecodes.en import LANGUAGE_NAMES
from .base import WiktionaryProcessor


PROCESSOR_UNMAPPED_POS_HEADINGS = UNMAPPED_POS_HEADINGS | {"nouns"}


class ENWiktionaryProcessor(WiktionaryProcessor):
    must_have_part_of_speech = True
    empty_definitions_list_if_no_definitions_found = False

    template_to_object_mapper = TEMPLATE_TO_OBJECT
    language_section_regex = r"^==\s*([^=]+?)\s*==$"

    all_importers = all_importers

    @property
    def processor_language(self):
        return "en"

    @property
    def language(self):
        return self.processor_language

    def __init__(self, test=False, verbose=False):
        super(ENWiktionaryProcessor, self).__init__(test=test, verbose=verbose)
        self.verbose = True
        self.text_set = False
        self.test = test
        self.postran = {
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
        self.regexesrep = [
            (r"\{\{l\|en\|(.*)\}\}", "\\1"),
            (r"\{\{vern\|(.*)\}\}", "\\1"),
            (r"\{\{lb\|(.*)|(.*)\}\}", ""),
            (r"\{\{n\-g\|(.*)\}\}", "\\1"),
            (r"\{\{ng\|(.*)\}\}", "\\1"),
            (r"\{\{non-gloss\|(.*)\}\}", "\\1"),
            (r"\{\{gloss\|(.*)\}\}", "\\1"),
            (r"\{\{g(?:l|loss)?\|(.*?)\}\}", "\\1"),
            (r"\[\[(.*)#(.*)\|?[.*]?\]?\]?", "\\1"),
            (r"\{\{(.*)\}\}", ""),
            (r"\[\[(.*)\|(.*)\]\]", "\\1"),
            (r"\((.*)\)", ""),
        ]

        self.verbose = verbose

        self.code = LANGUAGE_NAMES

        self.citations = {}
        self.examples = {}

    def lang2code(self, l):
        """
        Convert language name to its ISO code (2 or 3 characters
        :param l:
        :return:
        """
        return self.code[l]

    @wikicode_parse_session()
    def get_additional_data(
        self,
        page_section: str,
        language: str,
        part_of_speech: str | None = None,
    ) -> dict:
        """
        Retrieve additional data thanks to parsers at api.importer.wiktionary.en
        :param page_section: Page section for one language. This assumes only ONE language section is being provided.
                             Failure to pass only one language may cause it to misbehave and return unexpected data.
                             This is due to the suppression of '----' to delimit language sections in addition to the
                             L2 section.
        :param language: target language. Made for additional check in the get_data() method. Must
        :return:
        """
        additional_data: dict[str, object] = {}
        for ImporterClass in self.all_importers:
            importer = ImporterClass()
            data = importer.get_data(
                self.title or importer.section_name,
                page_section,
                language,
                part_of_speech,
            )

            if not data:
                continue
            existing = additional_data.get(importer.data_type)
            if isinstance(existing, list) and isinstance(data, list):
                additional_data[importer.data_type] = list(
                    dict.fromkeys([*existing, *data])
                )
            else:
                additional_data[importer.data_type] = data

        return additional_data

    def get_descendant_tree(
        self,
        language: str,
        part_of_speech: str,
        max_nodes: int | None = None,
    ) -> list[DescendantNode]:
        """Return recursive descendants for processed-page previews only."""

        return DescendantImporter().get_tree_data(
            self.title,
            self.content or "",
            language,
            part_of_speech,
            max_nodes,
        )

    def extract_definition(self, part_of_speech, definition_line, advanced=False, **kw):
        if not advanced:  # No cleanup
            return definition_line

        return self.advanced_extract_definition(part_of_speech, definition_line)

    def advanced_extract_definition(
        self,
        part_of_speech,
        definition_line,
        cleanup_definition=True,
        translate_definitions_to_malagasy=False,
        human_readable_form_of_definition=True,
    ):
        """
        Retrieve definition from the wiki page.
        :param part_of_speech: targetted part of speech
        :param definition_line: definition line, should start with a "#"
        :param cleanup_definition: remove links/templates?
        :param translate_definitions_to_malagasy: translate to malagasy? (valid for templates)
        :param human_readable_form_of_definition: put the form-of definition as a sentence
        :return:
        """
        new_definition_line = definition_line
        # No cleanup for definition
        if not cleanup_definition:
            return definition_line

        # Clean up non-needed template to improve readability.
        # In case these templates are needed, integrate your code above this part.
        for regex, replacement in self.regexesrep:
            new_definition_line = re.sub(regex, replacement, new_definition_line)

        if new_definition_line != "":
            return definition_line

        if human_readable_form_of_definition:
            try:
                if part_of_speech in self.template_to_object_mapper:
                    elements = templates_parser.get_elements(
                        self.template_to_object_mapper[part_of_speech],
                        definition_line,
                    )
                    new_definition_line = (
                        elements.to_definition("mg")
                        if translate_definitions_to_malagasy
                        else elements.to_definition(self.processor_language)
                    )
            except ParserNotFoundError:
                new_definition_line = definition_line
        # print(definition_line, new_definition_line)
        return new_definition_line

    def get_all_entries(
            self,
            keep_native_entries=False,
            get_additional_data=False,
            cleanup_definitions=False,
            translate_definitions_to_malagasy=False,
            human_readable_form_of_definition=True,
            **kw,
    ) -> list:

        """
        Retrieves all necessary information in the form of a list of Entry objects
        :param keep_native_entries:
        :param get_additional_data:
        :param cleanup_definitions:
        :param translate_definitions_to_malagasy:
        :param human_readable_form_of_definition:
        :param kw:
        :return:
        """
        content = self.content
        content = re.sub("{{l/en\\|(.*)}}", "\\1 ", content)  # remove {{l/en}}
        lines = self._coalesce_multiline_list_items(content.split("\n"))

        self.citations = {}
        self.examples = {}

        definitions, lines_by_language = self._process_lines(
            lines, cleanup_definitions, translate_definitions_to_malagasy,
            human_readable_form_of_definition, **kw
        )

        return self._build_entries(definitions, lines_by_language, get_additional_data)

    @staticmethod
    def _coalesce_multiline_list_items(lines: list[str]) -> list[str]:
        """Join definition-list items whose templates span source lines."""

        joined_lines: list[str] = []
        buffer: list[str] = []
        template_depth = 0
        for line in lines:
            if buffer:
                buffer.append(line)
                template_depth += line.count("{{") - line.count("}}")
                if template_depth <= 0:
                    joined_lines.append("\n".join(buffer))
                    buffer = []
                continue

            if line.startswith("#"):
                template_depth = line.count("{{") - line.count("}}")
                if template_depth > 0:
                    buffer = [line]
                    continue
            joined_lines.append(line)

        if buffer:
            joined_lines.append("\n".join(buffer))
        return joined_lines


    def _process_lines(self, lines, cleanup_definitions, translate_definitions_to_malagasy,
                       human_readable_form_of_definition, **kw):
        """Process all lines to extract definitions and organize content by language"""
        last_language_code = None
        last_part_of_speech = None
        definitions = {}
        lines_by_language = {}
        last_definition_map = {}
        last_citation_map = {}

        for line_number, line in enumerate(lines):
            # Handle language section headers
            if language_matched := re.match(self.language_section_regex, line):
                language_name = language_matched.groups()[0].strip()
                try:
                    last_language_code = self.lang2code(language_name)
                    last_part_of_speech = None  # Reset part of speech for the language section
                except KeyError:
                    if self.debug:
                        print(f"Could not determine code: {language_name}")
                    last_language_code = None

            if self.debug:
                print("<", last_language_code, last_part_of_speech, line_number, ">", line)

            # Skip if no valid language code
            if not last_language_code:
                continue

            # Add to lines per language
            if last_language_code in lines_by_language:
                lines_by_language[last_language_code].append(line)
            else:
                lines_by_language[last_language_code] = [line]

            # Update part of speech
            current_part_of_speech = self.get_part_of_speech(line)
            if current_part_of_speech is not None:
                last_part_of_speech = current_part_of_speech
            elif section_match := re.fullmatch(
                r"={3,6}\s*(.*?)\s*={3,6}", line
            ):
                section_title = re.sub(
                    r"\s+\d+(?:\.\d+)*$", "", section_match.group(1)
                ).casefold()
                if section_title in PROCESSOR_UNMAPPED_POS_HEADINGS:
                    last_part_of_speech = None

            definition_match = re.match(
                r"^(#+)(?![:*#])\s*(.+)$", line, re.DOTALL
            )
            example_match = re.match(r"^(#+):\s*(.*)$", line, re.DOTALL)
            citation_match = re.match(r"^(#+)\*\s*(.*)$", line, re.DOTALL)

            # Process definition lines, including nested subsenses.
            if definition_match is not None:
                marker, definition_text = definition_match.groups()
                depth = len(marker)
                for context in list(last_definition_map):
                    context_language, context_pos, context_depth = context
                    if (
                        context_language == last_language_code
                        and context_pos == last_part_of_speech
                        and context_depth >= depth
                    ):
                        del last_definition_map[context]
                        last_citation_map.pop(context, None)
                definition = self._process_definition_line(
                    f"# {definition_text}", last_language_code, last_part_of_speech, definitions,
                    cleanup_definitions, translate_definitions_to_malagasy,
                    human_readable_form_of_definition, **kw
                )
                if definition:
                    definition_index = (
                        len(definitions[last_language_code][last_part_of_speech]) - 1
                    )
                    last_definition_map[
                        (last_language_code, last_part_of_speech, depth)
                    ] = (definition, definition_index)

            # Process usage examples.
            elif example_match is not None:
                marker, example_text = example_match.groups()
                if example_text.startswith(":"):
                    continue
                context = last_definition_map.get(
                    (last_language_code, last_part_of_speech, len(marker))
                )
                if context and (example := self._parse_example_line(example_text)):
                    _, definition_index = context
                    self.examples.setdefault(last_language_code, {}).setdefault(
                        last_part_of_speech, {}
                    ).setdefault(definition_index, []).append(example)

            # Process source-bearing quotations.
            elif citation_match is not None:
                marker, citation_text = citation_match.groups()
                context_key = (
                    last_language_code,
                    last_part_of_speech,
                    len(marker),
                )
                if citation_text.startswith(":"):
                    if citation_text.startswith("::"):
                        continue
                    pending_citation = last_citation_map.get(context_key)
                    passage = self._parse_example_line(
                        citation_text.lstrip(": ")
                    )
                    if (
                        pending_citation
                        and passage
                        and not pending_citation[0].get("text")
                    ):
                        citation, definition_index = pending_citation
                        citation["text"] = passage
                        self.examples.setdefault(
                            last_language_code, {}
                        ).setdefault(last_part_of_speech, {}).setdefault(
                            definition_index, []
                        ).append(passage)
                    continue
                context = last_definition_map.get(context_key)
                if context:
                    last_def, definition_index = context
                    citation = self._parse_citation_line(line)
                    if citation:
                        citation["definition"] = last_def
                        self.citations.setdefault(last_language_code, {}).setdefault(
                            last_part_of_speech, []
                        ).append(citation)
                        last_citation_map[context_key] = (
                            citation,
                            definition_index,
                        )
                        if citation.get("text"):
                            self.examples.setdefault(
                                last_language_code, {}
                            ).setdefault(last_part_of_speech, {}).setdefault(
                                definition_index, []
                            ).append(citation["text"])

            if self.debug:
                print(f"{line_number} [{last_part_of_speech}|{last_language_code}] : {line}")

        return definitions, lines_by_language


    def _process_definition_line(self, line, language_code, part_of_speech, definitions,
                                 cleanup_definitions, translate_definitions_to_malagasy,
                                 human_readable_form_of_definition, **kw):
        """Process a single definition line and add it to the definitions dictionary"""
        defn_line = line.lstrip("# ")

        if part_of_speech is None and self.must_have_part_of_speech:
            return

        defn_line = self.refine_definition(defn_line, language_code, part_of_speech)
        if not defn_line:
            return None

        defn_line = defn_line[0]
        definition = self.extract_definition(
            part_of_speech=part_of_speech,
            definition_line=defn_line,
            cleanup_definition=cleanup_definitions,
            translate_definitions_to_malagasy=translate_definitions_to_malagasy,
            human_readable_form_of_definition=human_readable_form_of_definition,
            advanced=kw.get("advanced", False),
        )

        if language_code not in definitions:
            definitions[language_code] = {}

        if part_of_speech in definitions[language_code]:
            definitions[language_code][part_of_speech].append(definition)
        else:
            definitions[language_code][part_of_speech] = [definition]
        return definition

    @staticmethod
    def _strip_code_keeping_bold(value) -> str:
        """Strip wikicode from a passage value while keeping bold emphasis.

        Quotation passages embolden the quoted headword; the markers are
        protected with a placeholder so ``strip_code`` keeps them intact.
        """
        raw = str(value)
        if "'''" not in raw:
            return value.strip_code().strip()
        # Private-use character: the C tokenizer truncates its input at NUL,
        # so the placeholder must be an ordinary printable code point.
        placeholder = "\ue000"
        stripped = (
            mwparserfromhell.parse(raw.replace("'''", placeholder))
            .strip_code()
            .strip()
        )
        return stripped.replace(placeholder, "'''")

    def _parse_citation_line(self, line: str) -> dict[str, str] | None:
        """Parse a citation line and return a dictionary with source and text"""
        citation_line = line.lstrip("#* ").strip()
        if not citation_line:
            return None

        wikicode = mwparserfromhell.parse(citation_line)
        templates = wikicode.filter_templates(recursive=False)

        if templates:
            tpl = templates[0]
            source_parts = []
            text = ""
            url = ""
            month = ""
            year = ""
            for param in tpl.params:
                name = str(param.name).strip().lower()
                stripped_value = param.value.strip_code().strip()
                if name in {"passage", "text", "quote"}:
                    text = self._strip_code_keeping_bold(param.value)
                elif name == "url":
                    url = stripped_value
                elif name in {"page", "pages"}:
                    if stripped_value:
                        source_parts.append((name, f"pejy {stripped_value}"))
                elif name == "month":
                    month = localize_citation_date(stripped_value)
                elif name == "year":
                    year = stripped_value
                elif name in {
                    "date",
                    "orig-date",
                    "origdate",
                    "publication-date",
                    "publicationdate",
                }:
                    source_parts.append((name, localize_citation_date(stripped_value)))
                elif name not in {
                    "pageurl",
                    "pagesurl",
                    "wikisource",
                    "language",
                    "lang",
                    "nocat",
                    "nodot",
                    "tr",
                    "sc",
                    "id",
                    "inline",
                    "1",
                    "translation",
                    "transliteration",
                    "archiveurl",
                    "archive-url",
                    "archivedate",
                    "archive-date",
                    "accessdate",
                    "access-date",
                    "url-status",
                }:
                    source_parts.append((name, stripped_value))
            if month and year:
                source_parts.append(("date", f"{month} {year}"))
            elif month:
                source_parts.append(("month", month))
            elif year:
                source_parts.append(("year", year))

            def _citation_part_rank(part: tuple[str, str]) -> int:
                """Order citation parts as author, title, work, page, then date."""
                name, _ = part
                if name in {"author", "author2", "authors", "first", "last", "quotee"}:
                    return 0
                if name == "title":
                    return 1
                if name in {"page", "pages"}:
                    return 3
                if name in {
                    "date",
                    "month",
                    "orig-date",
                    "origdate",
                    "publication-date",
                    "publicationdate",
                    "year",
                }:
                    return 4
                return 2

            source_parts.sort(key=_citation_part_rank)
            url_used = False
            formatted_parts = []
            for name, value in source_parts:
                if not value:
                    continue
                if value.startswith("w:"):
                    # Interwiki work names ({{...|work=w:The New York Times}})
                    # become explicit Wikipedia links in the citation.
                    value = f"[[{value}|{value[len('w:'):]}]]"
                if name == "title" and url:
                    value = f"[{url} {value}]"
                    url_used = True
                formatted_parts.append(value)
            if url and not url_used:
                formatted_parts.append(url)
            source = ", ".join(formatted_parts)
            return {"source": source, "text": text}

        # No template; treat remaining text as citation text
        text = wikicode.strip_code().strip()
        if text:
            return {"source": "", "text": text}
        return None

    @staticmethod
    def _parse_example_line(line: str) -> str | None:
        """Return readable text from a direct usage-example line."""

        example_line = line.strip()
        if not example_line:
            return None

        wikicode = mwparserfromhell.parse(example_line)
        language_first_templates = {
            "afex",
            "collocation",
            "co",
            "coi",
            "example",
            "usex",
            "ux",
            "uxa",
            "uxi",
        }
        source_first_templates = {
            "ja-usex",
            "ja-x",
            "ko-usex",
            "ko-x",
            "th-usex",
            "th-x",
            "zh-usex",
            "zh-x",
        }
        example_templates = language_first_templates | source_first_templates
        for template in wikicode.filter_templates(recursive=True):
            template_name = str(template.name).strip().replace("_", " ").casefold()
            if template_name not in example_templates:
                continue
            for parameter_name in ("passage", "text", "quote", "example"):
                if template.has(parameter_name):
                    text = ENWiktionaryProcessor._strip_code_keeping_bold(
                        template.get(parameter_name).value
                    )
                    if text:
                        return text
            positional = [
                (int(str(param.name).strip()), param.value)
                for param in template.params
                if str(param.name).strip().isdigit()
            ]
            positional.sort()
            values = dict(positional)
            source_index = (
                1
                if template_name in source_first_templates or template.has("lang")
                else 2
            )
            if source_index in values:
                text = ENWiktionaryProcessor._strip_code_keeping_bold(
                    values[source_index]
                )
                if text:
                    return text

        plain_text = ENWiktionaryProcessor._strip_code_keeping_bold(wikicode)
        return plain_text or None


    @wikicode_parse_session()
    def _build_entries(self, definitions, lines_by_language, get_additional_data):
        """Build Entry objects from processed definitions and additional data"""
        entries = []

        for language_code in definitions:
            for pos, definitions_ in definitions[language_code].items():
                additional_data = None
                if get_additional_data and language_code in lines_by_language:
                    content = "\n".join(lines_by_language[language_code])
                    additional_data = self.get_additional_data(
                        content, language_code, pos
                    )

                entry = Entry(
                    entry=self.title,
                    part_of_speech=pos,
                    language=language_code,
                    definitions=definitions_,
                )

                combined_additional_data = {}

                if additional_data is not None and get_additional_data:
                    for data_type, data in additional_data.items():
                        if data:
                            combined_additional_data[data_type] = data

                if get_additional_data:
                    examples = self.examples.get(language_code, {}).get(pos, {})
                    aligned_examples = [
                        list(dict.fromkeys(examples.get(index, [])))
                        for index in range(len(definitions_))
                    ]
                    if any(aligned_examples):
                        combined_additional_data["examples"] = aligned_examples

                    citations = self.citations.get(language_code, {}).get(pos, [])
                    if citations:
                        combined_additional_data["citations"] = citations

                if combined_additional_data:
                    entry.additional_data = combined_additional_data

                entries.append(entry)

        return entries

    def get_part_of_speech(self, line, current_level=3, max_level=6):
        if current_level <= max_level:
            for en_pos, mg_pos in self.postran.items():
                if (
                    re.fullmatch(
                        "=" * current_level
                        + r"\s*"
                        + re.escape(en_pos)
                        + r"(?:\s+\d+(?:\.\d+)*)?\s*"
                        + "=" * current_level,
                        line,
                    )
                    is not None
                ):
                    return mg_pos

            return self.get_part_of_speech(line, current_level + 1)

        return None

    @staticmethod
    def refine_definition(definition, language=None, part_of_speech=None, **other_params) -> list:
        """Please define your function in api.translation_v2.functions.definitions.preprocessors and use them here."""

        if 'remove_all_templates' in other_params and other_params['remove_all_templates']:
            refined = refine_definition(definition, remove_all_templates=True)
        else:
            refined = refine_definition(definition)

        if 'drop_labels' in other_params and other_params['drop_labels']:
            labels = other_params['drop_labels']
            if language != ENWiktionaryProcessor.processor_language:
                # Remove obsolete and dated definitions for English, as they are not always relevant for language for which
                # we fetched the english definition due to the definition being a one-word.
                refined = drop_definitions_with_labels(*labels)(refined)

        refined = drop_all_labels(refined)


        return [refined] if refined.strip() else []

    def retrieve_translations(self) -> list:
        return TranslationImporter().get_data(self.content, self.language, self.title)
