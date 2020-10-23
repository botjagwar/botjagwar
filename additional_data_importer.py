import sys

import pywikibot
import requests

from page_lister import get_pages_from_category

backend = "http://10.0.0.10:8100"


class AdditionalDataImporter(object):
    def __init__(self, **parameters):
        def default_template_fetcher(template_title: str, wikipage: str, language: str):
            retrieved = []
            for line in wikipage.split('\n'):
                if "{{" + template_title + "|" + language in line:
                    line = line[line.find("{{" + template_title + "|" + language):]
                    data = line.split('|')[2]
                    data = data.replace('}}', '')
                    data = data.replace('{{', '')
                    retrieved.append(data)
            return retrieved

        if 'data' in parameters:
            self.data_type = parameters['data']

        if 'fetcher' in parameters:
            assert callable(parameters['fetcher'])
            self.get_data = parameters['fetcher']
        else:
            self.get_data = default_template_fetcher

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

    def fetch_additional_data_for_category(self, language, category_name):
        print(language, category_name)
        print('fetching words in database...')
        url = f"http://10.0.0.10:8100/word_with_additional_data"
        params = {
            'language': f'eq.{language}',
            'select': 'word,additional_data'
        }
        words = requests.get(url, params=params).json()
        # Database entries containing the data_type already defined.
        already_defined_pages = set([
            w['word']
            for w in words
            if self.data_type in set([
               dt['data_type'] for dt in
               w['additional_data']]
            )
        ])

        pages_defined_in_database = set([
            w['word']
            for w in words
        ])

        counter = 0

        # Wiki pages who may have not been parsed yet
        wikipages = [
            wikipage for wikipage
            in get_pages_from_category('en', category_name)
            if (wikipage.title() not in already_defined_pages
                and wikipage.title() in pages_defined_in_database)
        ]
        print(f"{category_name} now contains "
              f"{len(wikipages)} pages as "
              f"{len(already_defined_pages)} have been defined of the"
              f"{len(pages_defined_in_database)} pages currently defined in DB")
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
            print(additional_data_filenames)
            for additional_data in additional_data_filenames:
                data = {
                    'type': self.data_type,
                    'word_id': query[0]['id'],
                    'information': additional_data,
                }
                if not self.additional_word_information_already_exists(data['word_id'], additional_data):
                    response = requests.post(backend + '/additional_word_information', data=data)
                    if response.status_code != 201:
                        print(response.status_code)
                        print(response.text)
                else:
                    print('already exists and added.')

    def run(self, root_category: str, wiktionary=pywikibot.Site('en', 'wiktionary')):
        languages = {
            l['english_name']: l['iso_code']
            for l in requests.get(backend + '/language').json()
        }
        category = pywikibot.Category(wiktionary, root_category)
        for category in category.subcategories():
            name = category.title().replace('Category:', '')
            print(name)
            language_name = name.split()[0]
            if language_name in languages:
                iso = languages[language_name]
                print(f'Fetching for {language_name} ({iso})')
                self.fetch_additional_data_for_category(iso, category.title())
            else:
                print(f'Skipping for {language_name}...')


if __name__ == '__main__':
    args = sys.argv
    enwikt = pywikibot.Site('en', 'wiktionary')
    print(args)
    addi = AdditionalDataImporter(data=args[1])
    print(addi.data_type)
    addi.run(args[2])
