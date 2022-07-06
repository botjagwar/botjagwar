import re
from typing import List

from api.importer.wiktionary import \
    SubsectionImporter as BaseSubsectionImporter, \
    WiktionaryAdditionalDataImporter
from api.importer.wiktionary import use_wiktionary
from api.model.word import Translation

part_of_speech_translation = {
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


class SubsectionImporter(BaseSubsectionImporter):
    section_name = ''
    # True if the section contains a number e.g. Etymology 1, Etymology 2, etc.
    numbered = False
    level = 3

    def __init__(self, **params):
        super(SubsectionImporter, self).__init__(**params)

    def set_whole_section_name(self, section_name: str):
        self.section_name = section_name

    def get_data(self, template_title, wikipage: str, language: str) -> list:
        def retrieve_subsection(wikipage_, regex):
            retrieved_ = []
            target_subsection_section = re.search(regex, wikipage_)
            if target_subsection_section is not None:
                section = target_subsection_section.group()
                pos1 = wikipage_.find(section) + len(section)
                # section end is 2 newlines
                pos2 = wikipage_.find('\n\n', pos1)
                if pos2 != -1:
                    wikipage_ = wikipage_[pos1:pos2]
                else:
                    wikipage_ = wikipage_[pos1:]

                # More often than we'd like to admit,
                #   the section level for the given sub-section is one level deeper than expected.
                # As a consequence, a '=<newline>' can appear before the sub-section content.
                # That often happens for references, derived terms, synonyms, etymologies and part of speech.
                # We could throw an Exception,
                #   but there are 6.5M pages and God knows how many more cases to handle;
                #   so we don't: let's focus on the job while still keeping it simple.
                # Hence, the hack below can help the script fall back on its feet while still doing its job
                #   of fetching the subsection's content.
                # I didn't look for sub-sections that are actually 2 levels or more deeper than expected.
                # Should there be any of that, copy and adapt the condition.
                #   I didn't do it here because -- I.M.H.O -- Y.A.G.N.I right now.
                # My most sincere apologies to perfectionists.
                if wikipage_.startswith('=\n'):
                    wikipage_ = wikipage_[2:]

                retrieved_.append(wikipage_.lstrip('\n'))

            return retrieved_

        retrieved = []
        # Retrieving and narrowing to target section
        if self.numbered:
            number_rgx = ' [1-9]+'
        else:
            number_rgx = ''

        target_language_section = re.search(
            '==[ ]?' + self.iso_codes[language] + '[ ]?==', wikipage)
        if target_language_section is not None:
            section_begin = wikipage.find(target_language_section.group())
            section_end = wikipage.find('----', section_begin)
            if section_end != -1:
                lang_section_wikipage = wikipage = wikipage[section_begin:section_end]
            else:
                lang_section_wikipage = wikipage = wikipage[section_begin:]
        else:
            return []

        for regex_match in re.findall('=' * self.level + '[ ]?' + self.section_name + number_rgx + '=' * self.level,
                                      wikipage):
            retrieved += retrieve_subsection(wikipage, regex_match)
            wikipage = lang_section_wikipage

        returned_subsections = [s for s in retrieved if s]
        # print(returned_subsections)
        return returned_subsections  # retrieved


@use_wiktionary('en')
class ListSubsectionImporter(SubsectionImporter):
    def get_data(self, template_title, content: str, language: str) -> List[str]:
        subsection_data = SubsectionImporter.get_data(
            self, template_title, content, language)
        retrieved = []
        for subsection_item in subsection_data:
            if '*' in subsection_item:
                for item in subsection_item.split('*'):
                    if item.strip() == '':
                        continue

                    if '[[Thesaurus:' in item:
                        continue
                    if '{{l|' + language in item:
                        for data in re.findall(
                                '{{l\\|' + language + '\\|([0-9A-Za-z- ]+)}}', item):
                            retrieved.append(data)
                    elif '[[' in item and ']]' in item:
                        for data in re.findall(
                                '\\[\\[([0-9A-Za-z- ]+)\\]\\]', item):
                            retrieved.append(data)
                    else:
                        retrieved.append(item.strip())

        return list(set(retrieved))


class SynonymImporter(ListSubsectionImporter):
    level = 5
    data_type = 'synonym'
    section_name = 'Synonyms'


@use_wiktionary('en')
class EtymologyImporter(SubsectionImporter):
    level = 3
    data_type = 'etym/en'
    numbered = True
    section_name = 'Etymology'


@use_wiktionary('en')
class ReferencesImporter(SubsectionImporter):
    level = 3
    data_type = 'reference'
    section_name = 'References'
    filter_list = [
        '<references',  # References defined elsewhere
        '[[category:',  # Category section caught
        '==',  # Section caught
        '{{c|',  # Categorisation templates
        '{{comcatlite|'  # Commons category
    ]

    def has_filtered_element(self, ref):
        if ref.startswith('|'):
            return True

        for element in self.filter_list:
            if element in ref.lower():
                return True

        return False

    def get_data(self, template_title, wikipage: str, language: str):
        refs = super(
            ReferencesImporter,
            self).get_data(
            template_title,
            wikipage,
            language)
        refs_to_return = []
        returned_references = ''.join(refs)
        for ref_line in returned_references.split('\n'):
            if ref_line == '':
                continue

            if not self.has_filtered_element(ref_line):
                if ref_line.startswith('* '):
                    refs_to_return.append(ref_line.lstrip('* '))
                else:
                    refs_to_return.append(ref_line)

        return refs_to_return


class FurtherReadingImporter(ReferencesImporter):
    section_name = 'Further reading'
    data_type = 'further_reading'


class AlternativeFormsImporter(ListSubsectionImporter):
    level = 4
    data_type = 'alternative_form'
    section_name = 'Alternative forms'


class AntonymImporter(ListSubsectionImporter):
    level = 4
    data_type = 'antonym'
    section_name = 'Antonyms'


class DerivedTermsImporter(ListSubsectionImporter):
    level = 4
    data_type = 'derived'
    section_name = 'Derived terms'

    def get_data(self, template_title, content: str, language: str):
        subsection_data = SubsectionImporter.get_data(
            self, template_title, content, language)
        retrieved = []
        for subsection_item in subsection_data:
            # Simple list
            if '*' in subsection_item:
                for item in subsection_item.split('*'):
                    if '[[Thesaurus:' in item:
                        continue
                    if '{{l|' + language in item:
                        for data in re.findall(
                                '{{l\\|' + language + '\\|([0-9A-Za-z- ]+)}}', item):
                            retrieved.append(data)
                    elif '[[' in item and ']]' in item:
                        for data in re.findall(
                                '\\[\\[([0-9A-Za-z- ]+)\\]\\]', item):
                            retrieved.append(data)

            # List in a template
            for template_name in [f'der{d}' for d in range(1, 5)] +\
                                 ['der-bottom', 'der-top', 'der-top3'] +\
                                 [f'der-mid{d}' for d in range(1, 5)] +\
                                 [f'col{d}' for d in range(1, 6)]:
                if ('{{' + template_name + '|' + language) in subsection_item:
                    for item in subsection_item.split('\n'):
                        if item.startswith('|'):
                            if '#' in item:
                                item = item[:item.find('#')]
                            if '}}' in item:
                                item = item.replace('}}', '')

                            item = item.lstrip('|')
                            retrieved.append(item.strip())
                        elif item == '}}':
                            break

        return list(set(retrieved))


class DerivedTermsL5Importer(DerivedTermsImporter):
    level = 5


class PronunciationImporter(SubsectionImporter):
    level = 3
    data_type = 'pronunciation'
    section_name = 'Pronunciation'

    def get_data(self, template_title, wikipage: str, language: str) -> list:
        parent_class_data = super(PronunciationImporter, self).get_data(template_title, wikipage, language)
        pronunciations_list = []
        buffer = ''
        if len(parent_class_data):
            for line in parent_class_data[0].split('\n'):
                if line.startswith('*'):
                    pronunciations_list.append(line.strip('*').strip())
                else:
                    buffer += line

        if buffer:
            pronunciations_list.append(buffer)

        pronunciations = []
        for pron in pronunciations_list:
            if '-IPA' in pron:
                pronunciations.append(pron)
            if '-pron' in pron:
                pronunciations.append(pron)
            if '{{IPA|' in pron:
                pronunciations.append(pron)

        return pronunciations


class HeadwordImporter(WiktionaryAdditionalDataImporter):
    data_type = 'headwords'
    section_name = None

    possible_headword_affixes = [
        'verb', 'noun', 'adj', 'proper noun', 'det',
        'phrase', 'num', 'prefix', 'suffix', ''
    ]

    def get_data(self, template_title: str, wikipage: str, language: str) -> list:
        template_lines = []
        for line in wikipage.split('\n'):
            for headword_affix in self.possible_headword_affixes:
                if line.startswith('{{' + language + '-' + headword_affix):
                    template_lines.append(line)

        return list(set(template_lines))


class TranslationImporter(WiktionaryAdditionalDataImporter):
    level = 4
    data_type = 'translations'
    section_name = 'Translations'

    def get_data(self, wikipage: str, language: str, page_name: str = '') -> List[Translation]:
        """
        Warning: Will need reworking as this does not retrieve the specific definition that's  being translated in a
        given entry. If a definition is not specified, use the page name as the "definition".
        :return:
        """

        # Main regex to retrieve a given translation. Most of entries use this format
        regex = r'\{\{t[\+]?\|([A-Za-z]{2,3})\|(.*?)\}\}'

        translations = {}
        entries = []
        content = re.sub(
            "{{l/en\\|(.*)}}",
            "\\1 ",
            wikipage)  # remove {{l/en}}

        # Find the language section
        inside_translation_section = False
        for language in re.findall("[\n]?==[ ]?([A-Za-z]+)[ ]?==\n", content):
            last_part_of_speech = None
            content = content[content.find('==%s==' % language):]
            lines = content.split('\n')
            for line in lines:
                for en_pos, mg_pos in part_of_speech_translation.items():
                    if '===' + en_pos in line:
                        last_part_of_speech = mg_pos

                if '{{trans-top' in line:
                    definition = line.strip('{{trans-top')
                    if definition[0] == '|':
                        definition = definition.strip('|')
                    elif not definition.strip('}}'):
                        definition = page_name

                    definition = definition.strip('}}')
                    inside_translation_section = True
                    continue

                if '{{trans-mid' in line:
                    continue

                if '{{trans-bottom' in line:
                    inside_translation_section = False

                if inside_translation_section and len(re.findall(regex, line)) != 0:
                    for language_code, translation in re.findall(regex, line):
                        translation = translation[:translation.find('|')] if translation.find(
                            '|') != -1 else translation
                        if last_part_of_speech in translations:
                            translations[last_part_of_speech].append(
                                (language_code, translation, definition))
                        else:
                            translations[last_part_of_speech] = [
                                (language_code, translation, definition)]

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
    data_type = 'transcription'
    section_name = None

    def get_data(self, template_title: str, wikipage: str, language: str) -> list:
        template_lines = []
        headword_importer = HeadwordImporter()
        headwords = headword_importer.get_data(template_title, wikipage, language)
        for headword in headwords:
            if 'tr=' in headword:
                begin = headword.find('tr=') + 3
                end = headword.find('|', begin)
                if end == -1:
                    end = headword.find('}}', begin)
                template_lines.append(headword[begin:end].strip())

        return list(set(template_lines))


all_importers = [
    FurtherReadingImporter,
    AlternativeFormsImporter,
    AntonymImporter,
    DerivedTermsImporter,
    DerivedTermsL5Importer,
    PronunciationImporter,
    ReferencesImporter,
    EtymologyImporter,
    SynonymImporter,
    HeadwordImporter,
    TranscriptionImporter,
]
