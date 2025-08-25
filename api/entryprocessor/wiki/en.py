# coding: utf8
import re
import mwparserfromhell

from api.importer.wiktionary.en import all_importers, TranslationImporter
from api.model.word import Entry
from api.parsers.en import TEMPLATE_TO_OBJECT, templates_parser
from api.parsers.inflection_template import ParserNotFoundError

from api.translation_v2.functions.definitions.preprocessors import (
    refine_definition,
    drop_definitions_with_labels, drop_all_labels,
)

from conf.entryprocessor.languagecodes.en import LANGUAGE_NAMES
from .base import WiktionaryProcessor


class ENWiktionaryProcessor(WiktionaryProcessor):
    must_have_part_of_speech = True
    empty_definitions_list_if_no_definitions_found = False

    template_to_object_mapper = TEMPLATE_TO_OBJECT
    language_section_regex = "^==[ ]?([a-zA-Z'\ ]+)[ ]?==$"

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

    def lang2code(self, l):
        """
        Convert language name to its ISO code (2 or 3 characters
        :param l:
        :return:
        """
        return self.code[l]

    def get_additional_data(self, page_section, language) -> dict:
        """
        Retrieve additional data thanks to parsers at api.importer.wiktionary.en
        :param page_section: Page section for one language. This assumes only ONE language section is being provided.
                             Failure to pass only one language may cause it to misbehave and return unexpected data.
                             This is due to the suppression of '----' to delimit language sections in addition to the
                             L2 section.
        :param language: target language. Made for additional check in the get_data() method. Must
        :return:
        """
        additional_data = {}
        for ImporterClass in self.all_importers:
            importer = ImporterClass()
            additional_data[importer.data_type] = importer.get_data(
                importer.section_name, page_section, language
            )

        return additional_data

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
        lines = content.split("\n")

        self.citations = {}

        definitions, lines_by_language = self._process_lines(
            lines, cleanup_definitions, translate_definitions_to_malagasy,
            human_readable_form_of_definition, **kw
        )

        return self._build_entries(definitions, lines_by_language, get_additional_data)


    def _process_lines(self, lines, cleanup_definitions, translate_definitions_to_malagasy,
                       human_readable_form_of_definition, **kw):
        """Process all lines to extract definitions and organize content by language"""
        last_language_code = None
        last_part_of_speech = None
        definitions = {}
        lines_by_language = {}
        last_definition_map = {}

        for line_number, line in enumerate(lines):
            # Handle language section headers
            if language_matched := re.match(self.language_section_regex, line):
                language_name = language_matched.groups()[0]
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

            # Process definition lines
            if line.startswith("# "):
                definition = self._process_definition_line(
                    line, last_language_code, last_part_of_speech, definitions,
                    cleanup_definitions, translate_definitions_to_malagasy,
                    human_readable_form_of_definition, **kw
                )
                if definition:
                    last_definition_map[(last_language_code, last_part_of_speech)] = definition

            # Process citation lines
            elif line.startswith("#*"):
                last_def = last_definition_map.get((last_language_code, last_part_of_speech))
                if last_def:
                    citation = self._parse_citation_line(line)
                    if citation:
                        citation["definition"] = last_def
                        self.citations.setdefault(last_language_code, {}).setdefault(
                            last_part_of_speech, []
                        ).append(citation)

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

    def _parse_citation_line(self, line):
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
            for param in tpl.params:
                name = str(param.name).strip()
                value = str(param.value).strip()
                stripped_value = mwparserfromhell.parse(value).strip_code().strip()
                if name.lower() in {"passage", "text", "quote"}:
                    text = stripped_value
                elif name.lower() not in {
                    "url",
                    "pageurl",
                    "pagesurl",
                    "wikisource",
                    "language",
                    "lang",
                    "page",
                    "pages",
                    "nocat",
                    "nodot",
                    "tr",
                    "sc",
                    "id",
                    "inline",
                    "translation",
                    "transliteration",
                }:
                    source_parts.append(stripped_value)
            source = ", ".join([p for p in source_parts if p])
            return {"source": source, "text": text}

        # No template; treat remaining text as citation text
        text = mwparserfromhell.parse(citation_line).strip_code().strip()
        if text:
            return {"source": "", "text": text}
        return None


    def _build_entries(self, definitions, lines_by_language, get_additional_data):
        """Build Entry objects from processed definitions and additional data"""
        entries = []

        for language_code in definitions:
            additional_data = None
            if get_additional_data and language_code in lines_by_language:
                content = "\n".join(lines_by_language[language_code])
                additional_data = self.get_additional_data(content, language_code)

            for pos, definitions_ in definitions[language_code].items():
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
                    re.match(
                        "=" * current_level
                        + "[ ]?"
                        + en_pos
                        + "[ ]?"
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
