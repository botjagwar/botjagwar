import re

from api.importer.wiktionary import SubsectionImporter


class ListSubsectionImporter(SubsectionImporter):
    def get_data(self, template_title, content: str, language: str):
        subsection_data = SubsectionImporter.get_data(self, template_title, content, language)
        retrieved = []
        for subsection_item in subsection_data:
            if '*' in subsection_item:
                for item in subsection_item.split('*'):
                    if '[[Thesaurus:' in item:
                        continue
                    if '{{l|' + language in item:
                        for data in re.findall('{{l\|' + language + '\|([0-9A-Za-z- ]+)}}', item):
                            retrieved.append(data)
                    elif '[[' in item and ']]' in item:
                        for data in re.findall('\[\[([0-9A-Za-z- ]+)\]\]', item):
                            retrieved.append(data)
                    else:
                        retrieved.append(item)

        return list(set(retrieved))


class SynonymImporter(ListSubsectionImporter):
    level = 4
    data_type = 'synonym'
    section_name = 'Synonyms'


class EtymologyImporter(SubsectionImporter):
    level = 3
    data_type = 'etym/en'
    section_name = 'Etymology'


class ReferencesImporter(SubsectionImporter):
    level = 3
    data_type = 'reference'
    section_name = 'References'


class FurtherReadingImporter(ReferencesImporter):
    section_name = 'Further reading'


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
        subsection_data = SubsectionImporter.get_data(self, template_title, content, language)
        retrieved = []
        for subsection_item in subsection_data:
            # Simple list
            if '*' in subsection_item:
                for item in subsection_item.split('*'):
                    if '[[Thesaurus:' in item:
                        continue
                    if '{{l|' + language in item:
                        for data in re.findall('{{l\|' + language + '\|([0-9A-Za-z- ]+)}}', item):
                            retrieved.append(data)
                    elif '[[' in item and ']]' in item:
                        for data in re.findall('\[\[([0-9A-Za-z- ]+)\]\]', item):
                            retrieved.append(data)

            # List in a template
            for template_name in [f'der{d}' for d in range(1,5)] +\
                                 ['der-bottom', 'der-top', 'der-top3'] +\
                                 [f'der-mid{d}' for d in range(1,5)] +\
                                 [f'col{d}' for d in range(1,6)] :
                if ('{{' + template_name+ '|' + language) in subsection_item:
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
