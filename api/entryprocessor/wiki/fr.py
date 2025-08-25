# coding: utf8
import re

from api.importer.wiktionary.fr import all_importers
from api.model.word import Entry
from api.parsers.fr import TEMPLATE_TO_OBJECT
from api.parsers.fr import fr_definitions_parser as definitions_parser
from conf.entryprocessor.languagecodes.en import LANGUAGE_NAMES
from .base import WiktionaryProcessor, WiktionaryProcessorException

LANG_SECTION_REGEX = "==[ ]?{{langue\|([a-z]+)}}[ ]?=="
POS_FLEXION_SECTION_REGEX = "===[ ]?{{S\|([A-Za-z0-9 ]+)\|([a-z]+)\|flexion}}[ ]?==="
POS_LEMMA_SECTION_REGEX = "===[ ]?{{S\|([A-Za-z0-9 ]+)\|([a-z]+)}}[ ]?==="


class DefinitionProcessingConfig:
    """Configuration for definition processing options."""

    def __init__(self, cleanup_definition=True, translate_to_malagasy=True,
                 human_readable_form=True):
        self.cleanup_definition = cleanup_definition
        self.translate_to_malagasy = translate_to_malagasy
        self.human_readable_form = human_readable_form


class FRWiktionaryProcessor(WiktionaryProcessor):
    @property
    def processor_language(self):
        return "fr"

    @property
    def language(self):
        return self.processor_language

    def __init__(self, test=False, verbose=False):
        super(FRWiktionaryProcessor, self).__init__(test=test, verbose=verbose)
        self.verbose = True
        self.text_set = False
        self.test = test
        self.postran = {
            "verbe": "mat",
            "adjectif": "mpam",
            "adjectif interrogatif": "mpam",
            "adjectif possessif": "mpam",
            "adjectif exclamatif": "mpam",
            "conjonction": "mpampitohy",
            "déterminant": "mpam",
            "phrase": "fomba fiteny",
            "proverbe": "ohabolana",
            "adjectif numéral": "isa",
            "nom": "ana",
            "particule": "kianteny",
            "adverbe": "tamb",
            "pronom": "solo-ana",
            "pronom interrogatif": "solo-ana",
            "pronom possessif": "solo-ana",
            "pronom personnel": "solo-ana",
            "préposition": "mp.ank-teny",
            "contraction": "fanafohezana",
            "lettre": "litera",
            "nom propre": "ana-pr",
            "préfixe": "tovona",
            "romanisation": "rômanizasiona",
            "suffixe": "tovana",
            "symbole": "eva",
            "interjection": "tenim-piontanana",
            "infixe": "tsofoka",
        }
        self.verbose = verbose
        self.code = LANGUAGE_NAMES

    def get_additional_data(self, content, language) -> dict:
        """
        Retrieve additional data thanks to parsers at api.importer.wiktionary.en
        :param content: wiki page
        :param language: target language
        :return:
        """
        additional_data = {}
        for classe in all_importers:
            instance = classe()
            additional_data[instance.data_type] = instance.get_data(
                instance.section_name, content, language
            )

        return additional_data

    def extract_definition(self, part_of_speech, definition_line, advanced=False, **kw):
        return self.advanced_extract_definition(part_of_speech, definition_line)

    def advanced_extract_definition(self, part_of_speech, definition_line,
                                    config=None):
        """
        Retrieve definition from the wiki page.
        :param part_of_speech: targetted part of speech
        :param definition_line: definition line, should start with a "#"
        :param config: DefinitionProcessingConfig instance with processing options
        :return: processed definition line
        """
        if config is None:
            config = DefinitionProcessingConfig()

        processed_definition = definition_line

        if not part_of_speech.startswith("e-"):
            return processed_definition

        if not config.human_readable_form:
            return processed_definition

        processed_definition = self._convert_to_human_readable_form(
            part_of_speech, definition_line, config.translate_to_malagasy
        )

        return processed_definition

    def _convert_to_human_readable_form(self, part_of_speech, definition_line,
                                        translate_to_malagasy):
        """
        Convert form-of definitions to human-readable format.
        :param part_of_speech: part of speech to process
        :param definition_line: original definition line
        :param translate_to_malagasy: whether to translate to Malagasy
        :return: human-readable definition
        """
        try:
            if part_of_speech not in TEMPLATE_TO_OBJECT:
                return definition_line

            elements = definitions_parser.get_elements(
                TEMPLATE_TO_OBJECT[part_of_speech], definition_line
            )
            print(elements.__dict__)

            target_language = "mg" if translate_to_malagasy else self.processor_language
            return elements.to_definition(target_language)

        except Exception as error:
            return definition_line

    def get_all_entries(self, get_additional_data=False, **kw) -> list:

        """
        Retrieves all necessary information in the form of a list of Entry objects
        :param get_additional_data:
        :param kw:
        :return:
        """
        entries = []

        for language_section in re.findall(LANG_SECTION_REGEX, self.content):
            language_entries = self._parse_language_sections(language_section, get_additional_data)
            entries.extend(language_entries)

        return entries

    def _parse_language_sections(self, language_section, get_additional_data):
        """Parse a single language section and return entries for that language"""
        entries = []
        last_language_code = language_section[0]

        # Extract section content
        init_str = "== {{langue|%s}} ==" % language_section
        section_init = self.content.find(init_str)
        section_end = self.content.find("== {{langue|", section_init + len(init_str))

        if section_end != -1:
            section_content = self.content[section_init:section_end]
        else:
            section_content = self.content[section_init:]

        # Parse the section content
        definitions_dict, examples = self._parse_section_content(section_content.split("\n"))

        # Get additional data if requested
        additional_data = None
        if get_additional_data:
            additional_data = self.get_additional_data(section_content, last_language_code)

        # Create entries from parsed definitions
        entries = self._create_entries_from_definitions(
            definitions_dict, last_language_code, additional_data, get_additional_data
        )

        return entries

    def _parse_section_content(self, lines):
        """Parse lines within a language section to extract definitions and examples"""
        definitions_dict = {}
        examples = {}
        last_part_of_speech = None
        last_definition = None

        for line in lines:
            # Language header parsing
            lang_section_match = re.match(LANG_SECTION_REGEX, line)
            if lang_section_match is not None:
                # Reset for new language (shouldn't happen in this context, but keeping for safety)
                definitions_dict = {}
                examples = {}
                last_part_of_speech = None
                continue

            # Part of speech parsing
            pos_section_match = re.match(POS_LEMMA_SECTION_REGEX, line)
            pos_flexion_section_match = re.match(POS_FLEXION_SECTION_REGEX, line)

            if pos_section_match is not None:
                last_part_of_speech = self.postran[pos_section_match.groups()[0]]
                definitions_dict = {}
                examples = {}
            elif pos_flexion_section_match is not None:
                last_part_of_speech = f"e-{self.postran[pos_flexion_section_match.groups()[0]]}"
                definitions_dict = {}
                examples = {}

            # Definition parsing
            elif line.startswith("# "):
                definition = line.strip("# ")
                last_definition = definition
                if last_part_of_speech in definitions_dict:
                    definitions_dict[last_part_of_speech].append(definition)
                else:
                    definitions_dict[last_part_of_speech] = [definition]

            # Example parsing
            elif line.startswith("#* "):
                example = line.strip("#* ")
                if last_definition in examples:
                    examples[last_definition].append(example)
                else:
                    examples[last_definition] = [example]

        return definitions_dict, examples

    def _create_entries_from_definitions(self, definitions_dict, language_code, additional_data, get_additional_data):
        """Create Entry objects from parsed definitions dictionary"""
        entries = []

        for pos, definitions in definitions_dict.items():
            entry = Entry(
                entry=self.title,
                part_of_speech=pos,
                language=language_code,
                definitions=definitions,
            )

            if additional_data is not None and get_additional_data:
                entry.additional_data = {}
                for data_type, data in additional_data.items():
                    if data:
                        entry.additional_data[data_type] = data

            entries.append(entry)

        return entries

    @staticmethod
    def refine_definition(definition, part_of_speech=None) -> list:
        TEMPLATE_PATTERNS = [
            r"\{\{lexique\|[a-zA-Z0-9\ \|]+\}\}",
            r"\{\{familier\|[a-zA-Z0-9\ \|]+\}\}",
            r"\{\{[a-zA-Z0-9\ \|]+\|[a-zA-Z0-9\ \|]+\}\}"
        ]
        UNWANTED_CHARS = "{}|"

        refined = FRWiktionaryProcessor._process_templates(definition, TEMPLATE_PATTERNS)
        refined = FRWiktionaryProcessor._process_wiki_links(refined, part_of_speech)

        for unwanted_char in UNWANTED_CHARS:
            refined = refined.replace(unwanted_char, "")
        refined = refined.strip()

        FRWiktionaryProcessor._validate_refined_definition(refined, UNWANTED_CHARS)

        return [refined]

    @staticmethod
    def _process_templates(definition, template_patterns):
        refined = definition
        for pattern in template_patterns:
            if match := re.match(pattern, definition):
                match_text = match.group()
                begin_pos = definition.find(match_text)
                if begin_pos != -1:
                    end_pos = definition.find("}}", begin_pos)
                    label_data = FRWiktionaryProcessor._extract_label_data(definition, begin_pos, end_pos)
                    if label_data:
                        refined = f"({label_data}) {definition[end_pos + 2:].strip()}"
                    else:
                        refined = definition[end_pos + 2:].strip()
        return refined

    @staticmethod
    def _extract_label_data(definition, begin_pos, end_pos):
        label_data = definition[begin_pos:end_pos]
        label_data = label_data.replace("_", "").replace("|", " ")
        print(label_data)

        if re.match(r"^([a-zA-Z0-9\,\ ]+)$", label_data):
            return label_data
        return None

    @staticmethod
    def _process_wiki_links(refined, part_of_speech):
        refined = re.sub(r"\[\[([\w ]+)\|[\w ]+\]\]", "\\1", refined)
        if part_of_speech is not None and not part_of_speech.startswith("e-"):
            refined = re.sub(r"\[\[([\w ]+)\]\]", "\\1", refined)
        return refined

    @staticmethod
    def _validate_refined_definition(refined, unwanted_chars):
        for character in unwanted_chars:
            if character in refined:
                raise WiktionaryProcessorException(
                    f"Refined definition still has unwanted characters : '{character}'"
                )

    def retrieve_translations(self) -> list:
        return []
        # return TranslationImporter().get_data(self.content, self.language, self.title)
