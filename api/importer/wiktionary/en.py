import re

from api.importer.wiktionary import \
    SubsectionImporter, \
    WiktionaryAdditionalDataImporter
from api.importer.wiktionary import use_wiktionary


@use_wiktionary('en')
class ListSubsectionImporter(SubsectionImporter):
    def get_data(self, template_title, content: str, language: str):
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
    TranscriptionImporter
]
