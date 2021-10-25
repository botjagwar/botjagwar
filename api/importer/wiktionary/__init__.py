import re

import pywikibot
import requests

from api.importer import AdditionalDataImporter
from api.servicemanager.pgrest import DynamicBackend
from page_lister import get_pages_from_category

dyn_backend = DynamicBackend()


def use_wiktionary(language):
    def wrap_use_wiki(cls):
        cls.wiki = pywikibot.Site(language, 'wiktionary')
        return cls

    return wrap_use_wiki


class WiktionaryAdditionalDataImporter(AdditionalDataImporter):

    def fetch_additional_data_for_category(self, language, category_name):
        url = dyn_backend.backend + "/word_with_additional_data"
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

        url = dyn_backend.backend + "/word"
        params = {
            'language': f'eq.{language}',
        }
        words = requests.get(url, params=params).json()
        pages_defined_in_database = set([
            w['word']
            for w in words
        ])
        self.counter = 0
        category_pages = set(
            [k.title() for k in get_pages_from_category('en', category_name)])
        # Wiki pages who may have not been parsed yet
        titles = (category_pages & pages_defined_in_database) - \
            already_defined_pages
        wikipages = set([
            pywikibot.Page(self.wiktionary, page) for page in titles
        ])

        # print(f"{len(wikipages)} pages from '{category_name}';\n"
        #       f"{len(already_defined_pages)} already defined pages "
        #       f"out of {len(category_pages)} pages in category\n"
        # f"and {len(pages_defined_in_database)} pages currently defined in
        # DB\n\n")
        for wikipage in wikipages:
            self.process_wikipage(wikipage, language)

    def process_wikipage(self, wikipage: pywikibot.Page, language: str):
        content = wikipage.get()
        title = wikipage.title()
        return self.process_non_wikipage(title, content, language)

    def run(
        self,
        root_category: str,
        wiktionary=pywikibot.Site(
            'en',
            'wiktionary')):
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
    def get_data(
            self,
            template_title: str,
            wikipage: str,
            language: str) -> list:
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
