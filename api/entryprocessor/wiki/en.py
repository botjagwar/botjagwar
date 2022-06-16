# coding: utf8
import re

from api.importer.wiktionary.en import all_importers, TranslationImporter
from api.model.word import Entry
from api.parsers import TEMPLATE_TO_OBJECT
from api.parsers import templates_parser
from api.parsers.inflection_template import ParserNotFoundError
from conf.entryprocessor.languagecodes import LANGUAGE_NAMES
from .base import WiktionaryProcessor


class ENWiktionaryProcessor(WiktionaryProcessor):
    @property
    def processor_language(self):
        return 'en'

    @property
    def language(self):
        return self.processor_language

    def __init__(self, test=False, verbose=False):
        super(ENWiktionaryProcessor, self).__init__(test=test, verbose=verbose)
        self.verbose = True
        self.text_set = False
        self.test = test
        self.postran = {
            'Verb': 'mat',
            'Adjective': 'mpam',
            'Conjunction': 'mpampitohy',
            'Determiner': 'mpam',
            'Idiom': 'fomba fiteny',
            'Phrase': 'fomba fiteny',
            'Proverb': 'ohabolana',
            'Number': 'isa',
            'Noun': 'ana',
            'Adjectival noun': 'mpam',
            'Particle': 'kianteny',
            'Adverb': 'tamb',
            'Root': 'fototeny',
            'Numeral': 'isa',
            'Pronoun': 'solo-ana',
            'Preposition': 'mp.ank-teny',
            'Contraction': 'fanafohezana',
            'Letter': 'litera',
            'Proper noun': 'ana-pr',
            'Prefix': 'tovona',
            'Romanization': 'rômanizasiona',
            'Suffix': 'tovana',
            'Symbol': 'eva',
            'Participle': 'ova-mat',
            'Interjection': 'tenim-piontanana',
            'Infix': 'tsofoka',
        }
        self.regexesrep = [
            (r'\{\{l\|en\|(.*)\}\}', '\\1'),
            (r'\{\{vern\|(.*)\}\}', '\\1'),
            (r'\{\{lb\|(.*)|(.*)\}\}', ''),
            (r'\{\{gloss\|(.*)\}\}', '\\1'),
            (r"\[\[(.*)#(.*)\|?[.*]?\]?\]?", "\\1"),
            (r"\{\{(.*)\}\}", ""),
            (r'\[\[(.*)\|(.*)\]\]', '\\1'),
            (r"\((.*)\)", "")]

        self.verbose = verbose

        self.code = LANGUAGE_NAMES

    def lang2code(self, l):
        """
        Convert language name to its ISO code (2 or 3 characters
        :param l:
        :return:
        """
        return self.code[l]

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
        if not advanced:  # No cleanup
            return definition_line

        return self.advanced_extract_definition(part_of_speech, definition_line)

    def advanced_extract_definition(self, part_of_speech, definition_line,
                                    cleanup_definition=True,
                                    translate_definitions_to_malagasy=False,
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
        # No cleanup for definition
        if not cleanup_definition:
            return definition_line

        # Clean up non-needed template to improve readability.
        # In case these templates are needed, integrate your code above this part.
        for regex, replacement in self.regexesrep:
            new_definition_line = re.sub(
                regex, replacement, new_definition_line)

        # Form-of definitions: they use templates that can be parsed using api.parsers module which is tentatively
        #   being integrated here to provide human-readable output for either English or Malagasy
        if new_definition_line == '':
            if human_readable_form_of_definition:
                try:
                    if part_of_speech in TEMPLATE_TO_OBJECT:
                        elements = templates_parser.get_elements(
                            TEMPLATE_TO_OBJECT[part_of_speech], definition_line)
                        if translate_definitions_to_malagasy:
                            new_definition_line = elements.to_definition('mg')
                        else:
                            new_definition_line = elements.to_definition(
                                self.processor_language)
                except ParserNotFoundError:
                    new_definition_line = definition_line
        else:
            return definition_line

        # print(definition_line, new_definition_line)
        return new_definition_line

    def get_all_entries(
        self,
        keepNativeEntries=False,
        get_additional_data=False,
        cleanup_definitions=False,
        translate_definitions_to_malagasy=False,
        human_readable_form_of_definition=True,
        **kw) -> list:
        """
        Retrieves all necessary information in the form of a list of Entry objects
        :param keepNativeEntries:
        :param get_additional_data:
        :param cleanup_definitions:
        :param translate_definitions_to_malagasy:
        :param human_readable_form_of_definition:
        :param kw:
        :return:
        """
        content = self.content
        entries = []
        content = re.sub("{{l/en\\|(.*)}}", "\\1 ", content)  # remove {{l/en}}
        for l in re.findall("[\n]?==[ ]?([A-Za-z]+)[ ]?==\n", content):
            last_part_of_speech = None
            ct_content = content
            try:
                last_language_code = self.lang2code(l)
            except KeyError:
                continue

            definitions = {}
            section_init = ct_content.find('==%s==' % l)
            section_end = ct_content.find('----', section_init)
            if section_end != -1:
                ct_content = ct_content[section_init:section_end]
            else:
                ct_content = ct_content[section_init:]

            lines = ct_content.split('\n')
            for line in lines:
                if last_part_of_speech is None:
                    last_part_of_speech = self.get_part_of_speech(line)

                # We assume en.wikt definitions start with a "# " and proceed to extract all definitions from there.
                # Definitions are then added as a list of strings then added as a list of strings. They are grouped
                #   by part of speech to ensure correctness, as we can only have one part of speech for a given entry.
                if line.startswith('# '):
                    defn_line = line
                    defn_line = defn_line.lstrip('# ')
                    if last_part_of_speech is None:
                        continue

                    definition = self.extract_definition(
                        last_part_of_speech,
                        defn_line,
                        cleanup_definition=cleanup_definitions,
                        translate_definitions_to_malagasy=translate_definitions_to_malagasy,
                        human_readable_form_of_definition=human_readable_form_of_definition,
                        advanced=kw['advanced'] if 'advanced' in kw else False
                    )
                    if last_part_of_speech in definitions:
                        definitions[last_part_of_speech].append(definition)
                    else:
                        definitions[last_part_of_speech] = [definition]

            # Fetch additional data if flag is set, else put it to none
            if get_additional_data:
                additional_data = self.get_additional_data(
                    ct_content, last_language_code)
            else:
                additional_data = None

            # Create the Entry object to add to the list
            for pos, definitions in definitions.items():
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

    def get_part_of_speech(self, line, current_level=3, max_level=6):
        if current_level <= max_level:
            for en_pos, mg_pos in self.postran.items():
                if re.match('=' * current_level + '[ ]?'
                            + en_pos +
                            '[ ]?' + '=' * current_level,
                            line) is not None:
                    return mg_pos

            return self.get_part_of_speech(line, current_level+1)

        return None

    @staticmethod
    def refine_definition(definition) -> list:
        definition = re.sub('\\[\\[([\\w]+)\\|[\\w]+\\]\\]', '\\1', definition)
        definition = re.sub('\\[\\[([\\w]+)\\]\\]', '\\1', definition)
        definition = re.sub('[Tt]o ', '', definition)
        definition = re.sub('[Aa] ', '', definition)
        definition = re.sub('[Of], ', '', definition)
        definition = re.sub('[Oo]f or relating ', '', definition)
        definition = definition.replace(', or ', ' or ')
        definition = definition.replace(', and ', ' and ')
        # for separator in ';,':
        #     definition = definition.replace(separator + ' ', '$')
        if definition.endswith('.'):
            definition = definition[:-1]

        return [definition]

    def retrieve_translations(self) -> list:
        return TranslationImporter().get_data(self.content, self.language, self.title)
