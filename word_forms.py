# coding: utf8
"""
See this comment about usage
https://github.com/radomd92/botjagwar/issues/6#issuecomment-361023958
"""
import os
import re
import sys

import pywikibot

from api.entryprocessor import WiktionaryProcessorFactory
from api.output import Output
from api.parsers import AdjectiveForm
from api.parsers import NounForm
from api.parsers import VerbForm
from api.parsers import get_lemma
from api.parsers import templates_parser
from api.servicemanager import LanguageServiceManager
from object_model.word import Entry
from page_lister import get_pages_from_category

SITENAME = 'wiktionary'
SITELANG = 'mg'
last_entry = 0

if __name__ == '__main__':
    language_code = sys.argv[1]
    category_name = sys.argv[2]
    template = sys.argv[3] if len(sys.argv) >= 4 else 'e-ana'

TEMPLATE_TO_OBJECT = {
    'e-ana': NounForm,
    'e-mpam-ana': AdjectiveForm,
    'e-mat': VerbForm,
    'ana': NounForm,
    'mpam-ana': AdjectiveForm,
    'mat': VerbForm,
}

TEMPLATE_TO_MG_CATEGORY = {
    'e-ana': "Endrik'anarana",
    'e-mpam-ana': "Endri-pamaritra anarana",
    'e-mat': "Endriky ny matoanteny",
}


def get_count():
    try:
        with open('user_data/%s-counter' % language_code, 'r') as f:
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


def get_malagasy_page_set():
    mg_category_name = TEMPLATE_TO_MG_CATEGORY[template] + " amin'ny teny " + get_malagasy_language_name(language_code)
    return set([p.title() for p in get_pages_from_category(SITELANG, mg_category_name)])


def get_english_page_set():
    return set([p.title() for p in get_pages_from_category('en', category_name)])


def save_count():
    with open('user_data/%s-counter' % language_code, 'w') as f:
        f.write(str(last_entry))


def create_non_lemma_entry(word, pos, code, definition):
    page_output = Output()
    mg_page = pywikibot.Page(pywikibot.Site(SITELANG, SITENAME), word)

    # Translate template's content into malagasy
    try:
        if pos not in TEMPLATE_TO_OBJECT:  # unsupported template
            return 0
        output_object_class = TEMPLATE_TO_OBJECT[pos]
        elements = templates_parser.get_elements(output_object_class, definition)
        malagasy_definition = elements.to_malagasy_definition()
        lemma = get_lemma(output_object_class, definition)
        print(elements, malagasy_definition, lemma)
    except (AttributeError, ValueError) as exc:
        print(exc)
        return 0

    # Do not create page if lemma does not exist
    mg_lemma_page = pywikibot.Page(pywikibot.Site(SITELANG, SITENAME), lemma)
    if not mg_lemma_page.exists():
        print('No lemma :/')
        return 0

    mg_entry = Entry(
        entry=word,
        part_of_speech=template,
        entry_definition=[malagasy_definition],
        language=code,
    )

    # Check ability to overwrite page
    if not os.path.isfile('/tmp/%s' % code):  # overwrite existing content!
        overwrite = False
    else:
        overwrite = True
        print(('PAGE OVERWRITING IS ACTIVE. DELETE /tmp/%s TO DISABLE IT MID-SCRIPT.' % code))

    # Create or update the generated page
    if mg_page.exists() and not overwrite:
        new_entry = page_output.wikipage(mg_entry, link=False)
        page_content = mg_page.get()
        if page_content.find('{{=%s=}}' % code) != -1:
            if page_content.find('{{-%s-|%s}}' % (template, code)) != -1:
                print('section already exists : No need to go further')
                return 0
            else:  # Add part of speech subsection
                page_content = re.sub(r'==[ ]?{{=%s=}}[ ]?==' % code, new_entry, page_content)
        else:  # Add language section
            page_content = new_entry + '\n' + page_content
    else:  # Create a new page.
        page_content = page_output.wikipage(mg_entry, link=False)

    pywikibot.output('\03{blue}%s\03{default}' % page_content)
    mg_page.put(page_content, 'Teny vaovao')
    return 1


def parse_word_forms():
    global language_code
    global category_name
    global last_entry
    last_entry = get_count()
    working_language = 'en'

    # Initialise processor class
    en_page_processor_class = WiktionaryProcessorFactory.create(working_language)
    en_page_processor = en_page_processor_class()

    # Get list of articles from category
    counter = 0
    mg_page_set = get_malagasy_page_set()
    en_page_set = get_english_page_set()
    working_set = set([p for p in en_page_set if p not in mg_page_set])
    total = len(working_set)
    for word_page in working_set:
        word_page = pywikibot.Page(pywikibot.Site(working_language, 'wiktionary'), word_page)
        pywikibot.output('▒▒▒▒▒▒▒▒▒▒▒▒▒▒ \03{green}%-25s\03{default} ▒▒▒▒▒▒▒▒▒▒▒▒▒▒' % word_page.title())
        counter += 1
        if last_entry > counter:
            print('moving on')
            continue
        print("%d / %d (%2.2f%%)" % (counter, total, 100.*counter/total))
        en_page_processor.process(word_page)
        entries = en_page_processor.getall(definitions_as_is=True)
        print(word_page, entries)
        for word, pos, code, definition in entries:
            last_entry += create_non_lemma_entry(word, template, code, definition)


if __name__ == '__main__':
    try:
        parse_word_forms()
    finally:
        save_count()
