# coding: utf8
"""
See this comment about usage
https://github.com/radomd92/botjagwar/issues/6#issuecomment-361023958
"""
import os
import re
import sys
import traceback
import pywikibot

from object_model.word import Entry

from api.entryprocessor import WiktionaryProcessorFactory
from api.output import Output
from api.parsers import get_lemma
from api.parsers import templates_parser
from api.parsers import AdjectiveForm
from api.parsers import VerbForm
from api.parsers import NounForm


SITENAME = 'wiktionary'
SITELANG = 'mg'
last_entry = 0
language_code = sys.argv[1]
category_name = sys.argv[2]
template = sys.argv[3] if len(sys.argv) >= 4 else 'e-ana'

TEMPLATE_TO_OBJECT = {
    'e-ana': NounForm,
    'e-mpam-ana': AdjectiveForm,
    'e-mat': VerbForm,
}


def get_count():
    try:
        with open('user_data/%s-counter' % language_code, 'r') as f:
            counter = int(f.read())
            return counter
    except IOError:
        return 0


def save_count():
    with open('user_data/%s-counter' % language_code, 'w') as f:
        f.write(str(last_entry))


def parse_word_forms():
    global language_code
    global category_name
    global last_entry
    last_entry = get_count()
    working_language = 'en'

    # Initialise processor class
    en_page_processor_class = WiktionaryProcessorFactory.create(working_language)
    en_page_processor = en_page_processor_class()
    page_output = Output()

    # Get list of articles from category
    nouns = pywikibot.Category(pywikibot.Site(working_language, SITENAME), category_name)
    counter = 0
    for word_page in nouns.articles():
        pywikibot.output('▒▒▒▒▒▒▒▒▒▒▒▒▒▒ \03{green}%-25s\03{default} ▒▒▒▒▒▒▒▒▒▒▒▒▒▒' % word_page.title())
        counter += 1
        if last_entry > counter:
            print('moving on')
            continue
        en_page_processor.process(word_page)
        entries = en_page_processor.getall(definitions_as_is=True)
        print(word_page, entries)
        entries = [entry for entry in entries if entry[2] == str(language_code)]
        for word, pos, language_code, definition in entries:
            last_entry += 1
            mg_page = pywikibot.Page(pywikibot.Site(SITELANG, SITENAME), word)

            # Translate template's content into malagasy
            try:
                output_object_class = TEMPLATE_TO_OBJECT[template]
                elements = templates_parser.get_elements(output_object_class, definition)
                malagasy_definition = elements.to_malagasy_definition()
                lemma = get_lemma(output_object_class, definition)
                print(elements, malagasy_definition, lemma)
            except (AttributeError, ValueError) as e:
                traceback.print_exc()
                continue

            # Do not create page if lemma does not exist
            mg_lemma_page = pywikibot.Page(pywikibot.Site(SITELANG, SITENAME), lemma)
            if not mg_lemma_page.exists():
                print('No lemma :/')
                continue

            mg_entry = Entry(
                entry=word,
                part_of_speech=template,
                entry_definition=[malagasy_definition],
                language=language_code,
            )

            # Check ability to overwrite page
            if not os.path.isfile('/tmp/%s' % language_code):  # overwrite existing content!
                overwrite = False
            else:
                overwrite = True
                print(('PAGE OVERWRITING IS ACTIVE. DELETE /tmp/%s TO DISABLE IT MID-SCRIPT.' % language_code))

            # Create or update the generated page
            if mg_page.exists() and not overwrite:
                new_entry = page_output.wikipage(mg_entry, link=False)
                page_content = mg_page.get()
                if page_content.find('{{=%s=}}' % language_code) != -1:
                    if page_content.find('{{-%s-|%s}}' % (template, language_code)) != -1:
                        print('section already exists : No need to go further')
                        continue
                    else:  # Add part of speech subsection
                        page_content = re.sub(r'==[ ]?{{=%s=}}[ ]?==' % language_code, new_entry, page_content)
                else:  # Add language section
                    page_content = new_entry + '\n' + page_content
            else:  # Create a new page.
                page_content = page_output.wikipage(mg_entry, link=False)

            pywikibot.output('\03{blue}%s\03{default}' % page_content)
            mg_page.put(page_content, 'Teny vaovao')


if __name__ == '__main__':
    try:
        parse_word_forms()
    finally:
        save_count()
