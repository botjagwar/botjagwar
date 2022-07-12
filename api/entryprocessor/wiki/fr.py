# coding: utf8
import re

from api.importer.wiktionary.fr import all_importers
from api.model.word import Entry
from api.parsers import TEMPLATE_TO_OBJECT
from api.parsers import definitions_parser
from conf.entryprocessor.languagecodes import LANGUAGE_NAMES
from .base import WiktionaryProcessor

LANG_SECTION_REGEX = "==[ ]?{{langue\|([a-z]+)}}[ ]?=="
POS_FLEXION_SECTION_REGEX = "===[ ]?{{S\|([A-Za-z0-9 ]+)\|([a-z]+)\|flexion}}[ ]?==="
POS_LEMMA_SECTION_REGEX = "===[ ]?{{S\|([A-Za-z0-9 ]+)\|([a-z]+)}}[ ]?==="


class FRWiktionaryProcessor(WiktionaryProcessor):
    @property
    def processor_language(self):
        return 'fr'

    @property
    def language(self):
        return self.processor_language

    def __init__(self, test=False, verbose=False):
        super(FRWiktionaryProcessor, self).__init__(test=test, verbose=verbose)
        self.verbose = True
        self.text_set = False
        self.test = test
        self.postran = {
            'verbe': 'mat',
            'adjectif': 'mpam',
            'adjectif interrogatif': 'mpam',
            'adjectif possessif': 'mpam',
            'adjectif exclamatif': 'mpam',
            'conjonction': 'mpampitohy',
            'déterminant': 'mpam',
            'phrase': 'fomba fiteny',
            'proverbe': 'ohabolana',
            'adjectif numéral': 'isa',
            'nom': 'ana',
            'particule': 'kianteny',
            'adverbe': 'tamb',
            'pronom': 'solo-ana',
            'pronom interrogatif': 'solo-ana',
            'pronom possessif': 'solo-ana',
            'pronom personnel': 'solo-ana',
            'préposition': 'mp.ank-teny',
            'contraction': 'fanafohezana',
            'lettre': 'litera',
            'nom propre': 'ana-pr',
            'préfixe': 'tovona',
            'romanisation': 'rômanizasiona',
            'suffixe': 'tovana',
            'symbole': 'eva',
            'interjection': 'tenim-piontanana',
            'infixe': 'tsofoka',
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
                instance.section_name, content, language)

        return additional_data

    def extract_definition(self, part_of_speech, definition_line, advanced=False, **kw):
        return self.advanced_extract_definition(part_of_speech, definition_line)

    def advanced_extract_definition(self, part_of_speech, definition_line,
                                    cleanup_definition=True,
                                    translate_definitions_to_malagasy=True,
                                    human_readable_form_of_definition=True
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

        # Form-of definitions: they use templates that can be parsed using api.parsers module which is tentatively
        #   being integrated here to provide human-readable output for either English or Malagasy
        if human_readable_form_of_definition:
            try:
                if part_of_speech in TEMPLATE_TO_OBJECT:
                    elements = definitions_parser.get_elements(
                        TEMPLATE_TO_OBJECT[part_of_speech], definition_line)
                    print(elements.__dict__)

                    if translate_definitions_to_malagasy:
                        new_definition_line = elements.to_definition('mg')
                    else:
                        new_definition_line = elements.to_definition(
                            self.processor_language)
            except SyntaxError:
                new_definition_line = definition_line

        # print(definition_line, new_definition_line)
        return new_definition_line

    def get_all_entries(self, get_additional_data=False, **kw) -> list:
        """
        Retrieves all necessary information in the form of a list of Entry objects
        :param get_additional_data:
        :param kw:
        :return:
        """
        content = self.content
        entries = []
        last_definition = None
        additional_data = None
        definitions_dict = {}
        examples = {}
        for language_section in re.findall(LANG_SECTION_REGEX, self.content):
            last_part_of_speech = None
            ct_content = content
            last_language_code = language_section[0]

            init_str = '== {{langue|%s}} ==' % language_section
            section_init = ct_content.find(init_str)
            section_end = ct_content.find('== {{langue|', section_init + len(init_str))
            if section_end != -1:
                ct_content = ct_content[section_init:section_end]
            else:
                ct_content = ct_content[section_init:]

            lines = ct_content.split('\n')

            for line in lines:
                ct_content = content
                # Language header parsing
                lang_section_match = re.match(LANG_SECTION_REGEX, line)
                if lang_section_match is not None:
                    last_language_code = lang_section_match.groups()[0]
                    # Reset part of speech and definitions for the new language
                    definitions_dict = {}
                    examples = {}
                    last_part_of_speech = None
                    ct_content = line

                # Part of speech parsing
                pos_section_match = re.match(POS_LEMMA_SECTION_REGEX, line)
                pos_flexion_section_match = re.match(POS_FLEXION_SECTION_REGEX, line)
                if pos_section_match is not None:
                    last_part_of_speech = self.postran[pos_section_match.groups()[0]]
                    # Reset definitions for part of speech
                    definitions_dict = {}
                    examples = {}
                elif pos_flexion_section_match is not None:
                    last_part_of_speech = 'e-' + self.postran[pos_flexion_section_match.groups()[0]]
                    # Reset definitions for part of speech
                    definitions_dict = {}
                    examples = {}

                # Definition parsing
                # We assume fr.wikt definitions start with a "# " and proceed to extract all definitions from there.
                # Definitions are then added as a list of strings then added as a list of strings. They are grouped
                #   by part of speech to ensure correctness, as we can only have one part of speech for a given entry.
                if line.startswith('# '):
                    definition = line.strip('# ')
                    # definition = self.extract_definition(last_part_of_speech, definition, advanced=True)
                    last_definition = definition
                    if last_part_of_speech in definitions_dict:
                        definitions_dict[last_part_of_speech].append(definition)
                    else:
                        definitions_dict[last_part_of_speech] = [definition]

                # Example parsing for a given definition
                if line.startswith('#* '):
                    example = line.strip('#* ')
                    if last_definition in examples:
                        examples[last_definition].append(example)
                    else:
                        examples[last_definition] = [example]

                # Fetch additional data if flag is set, else put it to none
                if get_additional_data:
                    additional_data = self.get_additional_data(
                        ct_content, last_language_code)
                else:
                    additional_data = None

            # Create the Entry object to add to the list
            for pos, definitions in definitions_dict.items():
                entry = Entry(
                    entry=self.title,
                    part_of_speech=pos,
                    language=last_language_code,
                    definitions=definitions,
                )
                if additional_data is not None and get_additional_data:
                    entry.additional_data = {}
                    for data_type, data in additional_data.items():
                        if data:
                            entry.additional_data[data_type] = data

                entries.append(entry)

        return entries

    def retrieve_translations(self) -> list:
        return []
        # return TranslationImporter().get_data(self.content, self.language, self.title)
