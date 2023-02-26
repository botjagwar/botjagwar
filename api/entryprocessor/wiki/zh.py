# coding: utf8
import re

from api.model.word import Entry
# from api.parsers import TEMPLATE_TO_OBJECT
# from api.parsers import templates_parser
# from api.parsers.inflection_template import ParserNotFoundError
from .base import WiktionaryProcessor

LANGUAGE_NAMES = {}


class ZHWiktionaryProcessor(WiktionaryProcessor):
    """
    Processor for zhwiktionary pages. This is a first iteration of the processor, inspired by `ENWiktionaryProcessor`,
    which should already allow you to parse a good fraction of zhwikt pages.

    WARNING: Unlike frwikt or mgwikt, zhwikt entry formatting is highly irregular. Some entries are formatted like
    enwikt and some others use zhwikt-specific formatting.
    Thus having a lot of common (duplicated) code from the `en.py` file should NOT be a reason to merge both source
    files. I like to keep their implementation separate, since they are independent projects, although they're both
    hosted by the WMF.
    """

    @property
    def processor_language(self):
        return 'zh'

    @property
    def language(self):
        return self.processor_language

    def __init__(self, test=False, verbose=False):
        super(ZHWiktionaryProcessor, self).__init__(test=test, verbose=verbose)
        self.verbose = True
        self.text_set = False
        self.test = test
        self.postran = {
            # Traditional characters
            '動詞': 'mat',
            '形容詞': 'mpam',
            '連詞': 'mpampitohy',
            '限定詞': 'mpam',
            '成語': 'fomba fiteny',
            '短語': 'fomba fiteny',
            '諺語': 'ohabolana',
            '數字': 'isa',
            '名詞': 'ana',
            '粒子': 'kianteny',
            '副詞': 'tamb',
            '根': 'fototeny',
            '代詞': 'solo-ana',
            '介詞': 'mp.ank-teny',
            '收縮': 'fanafohezana',
            '信': 'litera',
            '字首': 'tovona',
            '羅馬化': 'rômanizasiona',
            '後綴': 'tovana',
            '象徵': 'eva',
            '分詞': 'ova-mat',
            '欹': 'tenim-piontanana',
            '中綴': 'tsofoka',

            # Simplified characters
            '动词': 'mat',
            '形容词': 'mpam',
            '连词': 'mpampitohy',
            '限定词': 'mpam',
            '成语': 'fomba fiteny',
            '短语': 'fomba fiteny',
            '谚语': 'ohabolana',
            '数字': 'isa',
            '名词': 'ana',
            '副词': 'fototeny',
            '代词': 'mp.ank-teny',
            '介词': 'fanafohezana',
            '收缩': 'litera',
            '恰当的': 'rômanizasiona',
            '罗马化': 'eva',
            '后缀': 'ova-mat',
            '象征': 'tenim-piontanana',
            '分词': 'tsofoka',
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

    def get_additional_data(self, content, language) -> dict:
        """
        Retrieve additional data thanks to parsers at api.importer.wiktionary.en
        :param content: wiki page
        :param language: target language
        :return:
        """
        additional_data = {}
        # for classe in all_importers:
        #     instance = classe()
        #     additional_data[instance.data_type] = instance.get_data(
        #         instance.section_name, content, language)

        return additional_data

    def extract_definition(self, part_of_speech, definition_line, advanced=False, **kw):
        if not advanced:  # No cleanup
            return definition_line

        return self.advanced_extract_definition(part_of_speech, definition_line)

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
        last_part_of_speech = None
        for language_name in re.findall(r"[\n]?==[ ]?([⺀-⺙⺛-⻳⼀-⿕々〇〡-〩〸-〺〻㐀-䶵一-鿃豈-鶴侮-頻並-龎]+)[ ]?==\n",
                                        content):
            last_language_code = language_name
            ct_content = content
            definitions = {}
            section_init = ct_content.find('==%s==' % language_name)
            section_end = ct_content.find('----', section_init)
            if section_end != -1:
                ct_content = ct_content[section_init:section_end]
            else:
                ct_content = ct_content[section_init:]

            lines = ct_content.split('\n')
            for line in lines:
                if last_part_of_speech is None:
                    last_part_of_speech = self.get_part_of_speech(line)

                # We assume zh.wikt definitions start with a "# " and proceed to extract all definitions from there.
                # Definitions are then added as a list of strings then added as a list of strings. They are grouped
                #   by part of speech to ensure correctness, as we can only have one part of speech for a given entry.
                if line.startswith('# '):
                    defn_line = line
                    defn_line = defn_line.lstrip('# ')

                    definition = self.extract_definition(
                        definition_line=defn_line,
                        part_of_speech='ana',
                        cleanup_definition=cleanup_definitions,
                        translate_definitions_to_malagasy=translate_definitions_to_malagasy,
                        human_readable_form_of_definition=human_readable_form_of_definition,
                        advanced=False
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

            # many zhwikt entries are definition-less or definition formatting is inconsistent
            if not definitions:
                definitions[last_part_of_speech] = []

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

            return self.get_part_of_speech(line, current_level + 1)

        return None

    def retrieve_translations(self) -> list:
        return []
        # return TranslationImporter().get_data(self.content, self.language, self.title)
