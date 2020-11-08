import re

import pywikibot
import requests

from api.importer import AdditionalDataImporter
from api.servicemanager.pgrest import DynamicBackend
from page_lister import get_pages_from_category

dyn_backend = DynamicBackend()


class WiktionaryAdditionalDataImporter(AdditionalDataImporter):

    def fetch_additional_data_for_category(self, language, category_name):
        url = dyn_backend.backend + f"/word_with_additional_data"
        params = {
            'language': f'eq.{language}',
            'select': 'word,additional_data',
        }
        words = requests.get(url, params=params).json()
        # Database entries containing the data_type already defined.
        already_defined_pages = set([
            w['word'] for w in words
            if self.is_data_type_already_defined(w['additional_data'])
        ])

        url = dyn_backend.backend + f"/word"
        params = {
            'language': f'eq.{language}',
        }
        words = requests.get(url, params=params).json()
        pages_defined_in_database = set([
            w['word']
            for w in words
        ])
        self.counter = 0
        category_pages = set([k.title() for k in get_pages_from_category('en', category_name)])
        # Wiki pages who may have not been parsed yet
        titles = (category_pages & pages_defined_in_database) - already_defined_pages
        wikipages = set([
            pywikibot.Page(self.wiktionary, page) for page in titles
        ])

        # print(f"{len(wikipages)} pages from '{category_name}';\n"
        #       f"{len(already_defined_pages)} already defined pages "
        #       f"out of {len(category_pages)} pages in category\n"
        #       f"and {len(pages_defined_in_database)} pages currently defined in DB\n\n")
        for wikipage in wikipages:
            self.process_wikipage(wikipage, language)

    def process_wikipage(self, wikipage: pywikibot.Page, language: str):
        content = wikipage.get()
        title = wikipage.title()
        return self.process_non_wikipage(title, content, language)

    def run(self, root_category: str, wiktionary=pywikibot.Site('en', 'wiktionary')):
        self.wiktionary = wiktionary
        category = pywikibot.Category(wiktionary, root_category)
        for category in category.subcategories():
            name = category.title().replace('Category:', '')
            # print(name)
            language_name = name.split()[0]
            if language_name in self.languages:
                iso = self.languages[language_name]
                # print(f'Fetching for {language_name} ({iso})')
                self.fetch_additional_data_for_category(iso, category.title())
            # else:
                # print(f'Skipping for {language_name}...')


class TemplateImporter(WiktionaryAdditionalDataImporter):
    def get_data(self, template_title: str, wikipage: str, language: str) -> list:
        retrieved = []
        for line in wikipage.split('\n'):
            if "{{" + template_title + "|" + language in line:
                line = line[line.find("{{" + template_title + "|" + language):]
                data = line.split('|')[2]
                data = data.replace('}}', '')
                data = data.replace('{{', '')
                retrieved.append(data)

        return retrieved


class SubsectionImporter(WiktionaryAdditionalDataImporter):
    section_name = ''
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
                pos2 = wikipage_.find('\n\n', pos1)
                wikipage_ = wikipage_[pos1:pos2]
                retrieved_.append(wikipage_.lstrip('\n'))

            return retrieved_

        retrieved = []
        # Retrieving and narrowing to target section
        target_language_section = re.search('==[ ]?' + self.iso_codes[language] +'[ ]?==', wikipage)
        if target_language_section is not None:
            lang_section_wikipage = wikipage = wikipage[wikipage.find(
                target_language_section.group()):wikipage.find('----')]
        else:
            return []

        for regex_match in re.findall('=' * self.level + '[ ]?' + self.section_name
                                      + '[ ]?[1-9]?[ ]?' + '=' * self.level, wikipage):
            # print(regex_match)
            # Retrieving subsection
            retrieved += retrieve_subsection(wikipage, regex_match)
            wikipage = lang_section_wikipage

        returned_subsections = [s for s in retrieved if s]
        # print(returned_subsections)
        return returned_subsections  # retrieved
