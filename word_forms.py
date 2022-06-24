# coding: utf8
"""
See this comment about usage
https://github.com/radomd92/botjagwar/issues/6#issuecomment-361023958
"""
import os
import re
import sys
import time

import pywikibot
import requests

from api.entryprocessor import WiktionaryProcessorFactory
from api.importer import AdditionalDataImporter, AdditionalDataImporterError, backend as db_backend
from api.model.word import Entry
from api.output import Output
from api.page_lister import get_pages_from_category
from api.parsers import TEMPLATE_TO_OBJECT, FORM_OF_TEMPLATE
from api.parsers import templates_parser
from api.parsers.functions.postprocessors import POST_PROCESSORS
from api.parsers.inflection_template import ParserError
from api.servicemanager import LanguageServiceManager
from redis_wikicache import RedisSite, RedisPage

SITENAME = 'wiktionary'
SITELANG = 'mg'
last_entry = 0

if __name__ == '__main__':
    param_language_code = sys.argv[1]
    param_category_name = sys.argv[2]
    param_template = sys.argv[3] if len(sys.argv) >= 4 else 'e-ana'


TEMPLATE_TO_MG_CATEGORY = {
    'e-ana': "Endrik'anarana",
    'e-mpam-ana': "Endri-pamaritra anarana",
    'e-mat': "Endriky ny matoanteny",
}

PAGE_SET = set()


def get_count(lang_code_local=None):
    if lang_code_local is None:
        global language_code
        lang_code_local = language_code
    try:
        with open('user_data/%s-counter' % lang_code_local, 'r') as f:
            counter = int(f.read())
            return counter
    except IOError:
        return 0


def get_malagasy_language_name(language_code):
    language_service_manager = LanguageServiceManager()
    language_service_manager.spawn_backend()
    mg_name_request = language_service_manager.get_language(language_code)
    if mg_name_request.status_code == 404:
        raise Exception()
    else:
        return mg_name_request.json()['malagasy_name']


def get_malagasy_page_set(template=None):
    if template is None:
        template = param_template

    mg_category_name = TEMPLATE_TO_MG_CATEGORY[template] + \
        " amin'ny teny " + get_malagasy_language_name(language_code)
    return set([p.title()
               for p in get_pages_from_category(SITELANG, mg_category_name)])


def get_english_page_set(category_name=None):
    if category_name is None:
        category_name = param_category_name

    return set([p.title()
               for p in get_pages_from_category('en', category_name)])


def save_count():
    with open('user_data/%s-counter' % language_code, 'w') as f:
        f.write(str(last_entry))


def _get_malagasy_page_list():
    with open('user_data/mgwiktionary-latest-all-titles-in-ns0', 'r') as f:
        for line in f.readlines():
            PAGE_SET.add(line.strip())


def create_non_lemma_entry(entry: Entry):
    word, pos, code, definition = entry.entry, entry.part_of_speech, entry.language, entry.definitions[
        0]
    page_output = Output()
    mg_page = pywikibot.Page(pywikibot.Site(SITELANG, SITENAME), word)

    # Translate template's content into malagasy
    try:
        if pos not in TEMPLATE_TO_OBJECT:  # unsupported template
            print("Unsupported template")
            return 0

        output_object_class = TEMPLATE_TO_OBJECT[pos]
        try:
            elements = templates_parser.get_elements(
                output_object_class, definition)
        except Exception:
            return 1

        if code in POST_PROCESSORS:
            elements = POST_PROCESSORS[code](elements)

        if elements is None:
            print("No elements")
            return 0

        malagasy_definition = elements.to_malagasy_definition()
        lemma = elements.lemma
        # lemma = get_lemma(output_object_class, definition)
        print(elements, malagasy_definition, lemma)
    except ParserError as exc:
        print(exc)
        return 0

    # Do not create page if lemma does not exist
    if lemma:
        mg_lemma_page = pywikibot.Page(
            pywikibot.Site(SITELANG, SITENAME), lemma)
    else:
        return 1

    try:
        if not mg_lemma_page.exists():
            print('No lemma (%s) :/' % lemma)
            return 0
        else:
            broken_redirect = False
            while mg_lemma_page.isRedirectPage():
                mg_lemma_page = mg_lemma_page.getRedirectTarget()
                if not mg_lemma_page.exists():
                    broken_redirect = True
                    break

            if not broken_redirect:
                content = mg_lemma_page.get()
                if '{{=' + language_code + '=}}' not in content:
                    print('No lemma (%s) :/' % lemma)
                    return 0
            else:
                print('No lemma : broken redirect (%s)' % lemma)
                return 0
    except pywikibot.exceptions.InvalidTitle:  # doing something wrong at this point
        return 0
    except Exception as e:
        return 1

    form_of_template = FORM_OF_TEMPLATE[pos] if pos in FORM_OF_TEMPLATE else pos

    mg_entry = Entry(
        entry=word,
        part_of_speech=form_of_template,
        definitions=[malagasy_definition],
        language=code,
    )

    # Check ability to overwrite page
    if not os.path.isfile('/tmp/%s' % code):  # overwrite existing content!
        overwrite = False
    else:
        overwrite = True
        print(
            ('PAGE OVERWRITING IS ACTIVE. DELETE /tmp/%s TO DISABLE IT MID-SCRIPT.' % code))

    # Create or update the generated page
    if mg_page.exists() and not overwrite:
        new_entry = page_output.wikipage(mg_entry, link=False)
        page_content = mg_page.get()
        if page_content.find('{{=%s=}}' % code) != -1:
            if page_content.find(
                '{{-%s-|%s}}' %
                    (form_of_template, code)) != -1:
                print('section already exists : No need to go further')
                return 0
            else:  # Add part of speech subsection
                page_content = re.sub(
                    r'==[ ]?{{=%s=}}[ ]?==' %
                    code, new_entry, page_content)
        else:  # Add language section
            page_content = new_entry + '\n' + page_content
    else:  # Create a new page.
        page_content = page_output.wikipage(mg_entry, link=False)

    pywikibot.output('\03{blue}%s\03{default}' % page_content)
    try:
        mg_page.put(page_content, f'endriky ny teny [[{lemma}]]')
    except Exception:
        pass

    return 1


importer = AdditionalDataImporter(data='lemma')


def import_additional_data(entry: Entry) -> int:
    word, pos, code, definition = entry.entry, entry.part_of_speech, entry.language, entry.definitions[
        0]

    # Translate template's content into malagasy
    try:
        if pos not in TEMPLATE_TO_OBJECT:  # unsupported template
            print("Unsupported template")
            return 0

        output_object_class = TEMPLATE_TO_OBJECT[pos]
        try:
            elements = templates_parser.get_elements(
                output_object_class, definition)
        except Exception as exc:
            raise ParserError from exc

    except ParserError as exc:
        print(exc)
        return 0

    if code in POST_PROCESSORS:
        elements = POST_PROCESSORS[code](elements)

    if elements is None:
        print("No elements")
        return 0

    malagasy_definition = elements.to_malagasy_definition()
    lemma = elements.lemma

    def get_word_id_query():
        rq_params = {
            'word': 'eq.' + entry.entry,
            'language': 'eq.' + entry.language,
            'part_of_speech': 'eq.' + template.strip()
        }
        print(rq_params)
        response = requests.get(db_backend.backend + '/word', rq_params)
        return response.json()

    def post_new_word():
        rq_params = {
            'word': entry.entry,
            'language': entry.language,
            'part_of_speech': template.strip(),
            'date_changed': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        print(rq_params)
        response = requests.post(db_backend.backend + '/word', rq_params)
        if response.status_code >= 400:
            print(response.json())
            raise AdditionalDataImporterError(
                f'Response on post is unexpected: {response.status_code}')

    try:
        query = get_word_id_query()
        if len(query) > 0:
            word_id = query[0]['id']
            importer.write_additional_data(word_id, lemma)
        else:
            post_new_word()
            query = get_word_id_query()
            assert len(query) > 0
            if len(query) > 0:
                word_id = query[0]['id']
                importer.write_additional_data(word_id, lemma)

    except (KeyError, AdditionalDataImporterError) as err:
        print(err)

    print(elements, malagasy_definition, lemma)
    return 0


def perform_function_on_entry(function):
    def process():
        global language_code
        global category_name
        global last_entry
        last_entry = get_count()
        working_language = 'en'

        # Initialise processor class
        en_page_processor_class = WiktionaryProcessorFactory.create(
            working_language)
        en_page_processor = en_page_processor_class()

        # Get list of articles from category
        counter = 0
        mg_page_set = {}  # get_malagasy_page_set()
        en_page_set = get_english_page_set(category_name)
        working_set = set([p for p in en_page_set if p not in mg_page_set])
        total = len(working_set)
        for word_page in working_set:
            word_page = RedisPage(
                RedisSite(
                    working_language,
                    'wiktionary'),
                word_page,
                offline=False)
            # word_page = pywikibot.Page(pywikibot.Site(working_language, 'wiktionary'), word_page)
            pywikibot.output(
                '▒▒▒▒▒▒▒▒▒▒▒▒▒▒ \03{green}%-25s\03{default} ▒▒▒▒▒▒▒▒▒▒▒▒▒▒' %
                word_page.title())
            counter += 1
            if last_entry > counter:
                print('moving on')
                continue

            print(
                "%d / %d (%2.2f%%)" %
                (counter, total, 100. * counter / total))
            en_page_processor.process(word_page)
            entries = en_page_processor.get_all_entries(definitions_as_is=True)
            print(word_page, entries)
            for entry in entries:
                last_entry += function(entry)

        return last_entry

    return process


def parse_word_forms():
    return perform_function_on_entry(create_non_lemma_entry)()


def import_nonlemma_in_additional_data():
    return perform_function_on_entry(import_additional_data)()


if __name__ == '__main__':
    try:
        # get_malagasy_page_list()
        parse_word_forms()
        # import_nonlemma_in_additional_data()
    finally:
        save_count()
