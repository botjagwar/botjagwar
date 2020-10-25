import re

from additional_data_importer import SubsectionImporter


class SynonymImporter(SubsectionImporter):
    level = 4
    data_type = 'synonym'
    section_name = 'Synonyms'

    def get_data(self, template_title, wikipage: str, language: str):
        subsection_data = SubsectionImporter.get_data(self, template_title, wikipage, language)
        retrieved = []
        for subsection_item in subsection_data:
            if '*' in subsection_item:
                for item in subsection_item.split('*'):
                    if '[[Thesaurus:' in item:
                        continue
                    if '{{l|' + language in item:
                        for data in re.findall('{{l\|' + language + '\|([0-9A-Za-z-]+)}}', item):
                            retrieved.append(data)

        print('asdasd', retrieved)
        return list(set(retrieved))


class EtymologyImporter(SubsectionImporter):
    level = 3
    data_type = 'etym/en'
    section_name = 'Etymology'


if __name__ == '__main__':
    addi = SynonymImporter(dry_run=False)
    # import pywikibot
    # page = pywikibot.Page(pywikibot.Site('en', 'wiktionary'), 'malevolence')
    # data = addi.get_data('', page.get(), 'en')
    # print(data)
    addi.run('English nouns')

    # addi = SubsectionImporter(data='etym/en', dry_run=True)
    # addi.section_name = 'Etymology'
    # addi.run('Lemmas by language')
