# coding: utf8
import re

from api.importer.wiktionary.en import all_importers, TranslationImporter
from api.model.word import Entry
from api.parsers import TEMPLATE_TO_OBJECT
from api.parsers import templates_parser
from api.parsers.inflection_template import ParserNotFoundError
from conf.entryprocessor.languagecodes.en import LANGUAGE_NAMES
from .base import WiktionaryProcessor, WiktionaryProcessorException


class ENWiktionaryProcessor(WiktionaryProcessor):
    must_have_part_of_speech = True
    empty_definitions_list_if_no_definitions_found = False

    template_to_object_mapper = TEMPLATE_TO_OBJECT
    language_section_regex = "^==[ ]?([\w+ \-]+)[ ]?==$"

    all_importers = all_importers

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
            (r"\((.*)\)", "")
        ]

        self.verbose = verbose

        self.code = LANGUAGE_NAMES

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
        for classe in self.all_importers:
            instance = classe()
            additional_data[instance.data_type] = instance.get_data(
                instance.section_name, page_section, language)

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
                    if part_of_speech in self.template_to_object_mapper:
                        elements = templates_parser.get_elements(
                            self.template_to_object_mapper[part_of_speech], definition_line)
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
        keep_native_entries=False,
        get_additional_data=False,
        cleanup_definitions=False,
        translate_definitions_to_malagasy=False,
        human_readable_form_of_definition=True,
        **kw) -> list:
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
        entries = []
        content = re.sub("{{l/en\\|(.*)}}", "\\1 ", content)  # remove {{l/en}}
        lines = content.split('\n')
        last_language_code = None
        last_part_of_speech = None
        definitions = {}

        lines_by_language = {}  # Key is language, value are the content for that language

        for line_number, line in enumerate(lines):
            language_matched = re.match(self.language_section_regex, line)
            if language_matched:
                language_name = language_matched.groups()[0]
                try:
                    last_language_code = self.lang2code(language_name)
                    last_part_of_speech = None  # Reset part of speech for the language section
                except KeyError:
                    # print(f"Could not determine code: {language_name}")
                    pass

            # Add to the lines per language
            if last_language_code in lines_by_language:
                lines_by_language[last_language_code].append(line)
            else:
                lines_by_language[last_language_code] = [line]

            # Fetch part of speech for the language section
            current_part_of_speech = self.get_part_of_speech(line)
            if current_part_of_speech is not None:
                last_part_of_speech = current_part_of_speech

            # We assume en.wikt definitions start with a "# " and proceed to extract all definitions from there.
            # Definitions are then added as a list of strings then added as a list of strings. They are grouped
            #   by part of speech to ensure correctness, as we can only have one part of speech for a given entry.
            if line.startswith('# '):
                defn_line = line
                defn_line = defn_line.lstrip('# ')
                if last_part_of_speech is None and self.must_have_part_of_speech:
                    continue

                definition = self.extract_definition(
                    part_of_speech=last_part_of_speech,
                    definition_line=defn_line,
                    cleanup_definition=cleanup_definitions,
                    translate_definitions_to_malagasy=translate_definitions_to_malagasy,
                    human_readable_form_of_definition=human_readable_form_of_definition,
                    advanced=kw['advanced'] if 'advanced' in kw else False
                )
                if last_language_code not in definitions:
                    definitions[last_language_code] = {}

                if last_part_of_speech in definitions[last_language_code]:
                    definitions[last_language_code][last_part_of_speech].append(definition)
                else:
                    definitions[last_language_code][last_part_of_speech] = [definition]

        # entries may be definition-less or definition formatting is inconsistent
        for language_code in definitions:
            if get_additional_data and language_code in lines_by_language:
                content = '\n'.join(lines_by_language[language_code])
                additional_data = self.get_additional_data(content, language_code)
            else:
                additional_data = None

            for pos, definitions_ in definitions[language_code].items():
                entry = Entry(
                    entry=self.title,
                    part_of_speech=pos,
                    language=language_code,
                    definitions=definitions_,
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
    def refine_definition(definition, part_of_speech=None) -> list:
        # handle {{lb}} template calls
        refined = definition
        lb_template_rgxs = [
            r'\{\{l[b]?\|([a-zA-Z0-9\ ]{2,3})\|([\w ]+)'
            r'\{\{l[b]? [a-z]+\|([a-zA-Z0-9\ ]{2,3})\|([\w ]+)'
        ]
        for lb_template_rgx in lb_template_rgxs:
            lb_match = re.match(lb_template_rgx, definition)
            if lb_match:
                lb_match = lb_match.group()
                lb_begin = definition.find(lb_match)
                if lb_begin != -1:
                    lb_end = definition.find('}}', lb_begin)
                    label_data = definition[lb_begin:lb_end]
                    label_data = label_data.replace('_', '')
                    label_data = label_data.replace('|', ' ')
                    print(label_data)
                    # Ensure that no unexpected characters has been onboarded,
                    # if it's the case, just ditch the label information.
                    if re.match(r'^([a-zA-Z0-9\,\ ]+)$', label_data):
                        refined = f'({label_data}) ' + definition[lb_end + 2:].strip()
                    else:
                        refined = definition[lb_end + 2:].strip()

        # Handle {{gloss}}
        gloss_template_begin = refined.find('{{gloss|')
        if gloss_template_begin != -1:
            gloss_template_begin += len('{{gloss|')
            gloss_template_end = refined.find('}}', gloss_template_begin)
            refined = refined[gloss_template_begin:gloss_template_end]

        # Handle [[]] links
        refined = re.sub(r'\[\[([\w ]+)\|[\w ]+\]\]', '\\1', refined)
        refined = re.sub(r'\[\[([\w ]+)\]\]', '\\1', refined)

        unwanted_character = False
        for character in "{}[]|":
            if character in refined:
                unwanted_character = True
                break

        if unwanted_character:
            raise WiktionaryProcessorException("Refined definition still has unwanted characters : '" + character + "'")

        return [refined]

    def retrieve_translations(self) -> list:
        return TranslationImporter().get_data(self.content, self.language, self.title)
