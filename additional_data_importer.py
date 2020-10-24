import re
import sys

import pywikibot
import requests

from page_lister import get_pages_from_category

backend = "http://10.0.0.10:8100"


class AdditionalDataImporter(object):
    def __init__(self, **parameters):
        self.languages = {
            l['english_name']: l['iso_code']
            for l in requests.get(backend + '/language').json()
        }

        self.iso_codes = {
            v: k for k, v in self.languages.items()
        }

        if 'dry_run' in parameters:
            self.dry_run = parameters['dry_run']
        else:
            self.dry_run = False

        if 'data' in parameters:
            self.data_type = parameters['data']

    def additional_word_information_already_exists(self, word_id, information):
        data = {
            'type': 'eq.' + self.data_type,
            'word_id': 'eq.' + str(word_id),
            'information': 'eq.' + information,
        }
        response = requests.get(backend + '/additional_word_information', params=data)
        resp_data = response.json()
        print(resp_data)
        if resp_data:
            if 'word_id' in resp_data[0] \
                    and 'information' in resp_data[0] \
                    and 'type' in resp_data[0]:
                return True

        return False

    def get_data(self, template_title: str, wikipage: str, language: str) -> list:
        raise NotImplementedError()

    def is_data_type_already_defined(self, additional_data):
        for d in additional_data:
            if d['data_type'] == self.data_type:
                return True

        return False

    def fetch_additional_data_for_category(self, language, category_name):
        print(language, category_name)
        print('fetching words in database...')
        url = f"http://10.0.0.10:8100/word_with_additional_data"
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

        url = f"http://10.0.0.10:8100/word"
        params = {
            'language': f'eq.{language}',
        }
        words = requests.get(url, params=params).json()
        pages_defined_in_database = set([
            w['word']
            for w in words
        ])
        counter = 0
        category_pages = set([k.title() for k in get_pages_from_category('en', category_name)])
        # Wiki pages who may have not been parsed yet
        titles = (category_pages & pages_defined_in_database) - already_defined_pages
        wikipages = set([
            pywikibot.Page(self.wiktionary, page) for page in titles
        ])

        print(f"{len(wikipages)} pages from '{category_name}';\n"
              f"{len(already_defined_pages)} already defined pages "
              f"out of {len(category_pages)} pages in category\n"
              f"and {len(pages_defined_in_database)} pages currently defined in DB\n\n")
        for wikipage in wikipages:
            title = wikipage.title()
            counter += 1
            print(f'>>> {title} [#{counter}] <<<')
            rq_params = {
                'word': 'eq.' + title,
                'language': 'eq.' + language
            }
            response = requests.get(backend + '/word', rq_params)
            print(response.status_code)
            query = response.json()
            if not query:
                continue

            additional_data_filenames = self.get_data(self.data_type, wikipage.get(), language)
            assert isinstance(additional_data_filenames, list)
            print(additional_data_filenames)
            for additional_data in additional_data_filenames:
                data = {
                    'type': self.data_type,
                    'word_id': query[0]['id'],
                    'information': additional_data,
                }
                if not self.additional_word_information_already_exists(data['word_id'], additional_data):
                    if not self.dry_run:
                        response = requests.post(backend + '/additional_word_information', data=data)
                        if response.status_code != 201:
                            print(response.status_code)
                            print(response.text)
                    else:
                        print(data)
                else:
                    print('already exists and added.')

    def run(self, root_category: str, wiktionary=pywikibot.Site('en', 'wiktionary')):
        self.wiktionary = wiktionary

        category = pywikibot.Category(wiktionary, root_category)
        for category in category.subcategories():
            name = category.title().replace('Category:', '')
            print(name)
            language_name = name.split()[0]
            if language_name in self.languages:
                iso = self.languages[language_name]
                print(f'Fetching for {language_name} ({iso})')
                self.fetch_additional_data_for_category(iso, category.title())
            else:
                print(f'Skipping for {language_name}...')


class TemplateImporter(AdditionalDataImporter):
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


class SubsectionImporter(AdditionalDataImporter):
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
            print(regex_match)
            # Retrieving subsection
            retrieved += retrieve_subsection(wikipage, regex_match)
            wikipage = lang_section_wikipage

        returned_subsections = [s for s in retrieved if s]
        print(returned_subsections)
        return returned_subsections  # retrieved


if __name__ == '__main__':
    args = sys.argv
    print(args)
    addi = TemplateImporter(data=args[1])
    print(addi.data_type)
    addi.run(args[2])
