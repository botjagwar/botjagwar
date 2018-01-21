# coding: utf8

import re

import pywikibot

from models.word import Entry

from modules.entryprocessor import WiktionaryProcessorFactory
from modules.output import Output


CASES = {
    'nom': u'endriky ny lazaina',
    'acc': u'endrika teny fameno',
    'loc': u'endrika teny famaritan-toerana',
    'dat': u'mpanamarika ny tolorana',
    'gen': u'mpanamarika ny an\'ny tompo'
}
NUMBER = {
    's': u'singiolary',
    'p': u'ploraly',
}
SITENAME = 'wiktionary'
SITELANG = 'mg'

last_entry = 0

def get_count():
    with open('user_data/lv-counter', 'r') as f:
        counter = int(f.read())
        return counter


def save_count():
    with open('user_data/lv-counter', 'w') as f:
        f.write(str(last_entry))


def get_lemma(template_expr):
    for char in u'{}':
        template_expr = template_expr.replace(char, u'')
    parts = template_expr.split(u'|')
    if len(parts) != 4:
        raise ValueError()

    _, lemma, _, _= parts
    return lemma


def template_expression_to_malagasy_definition(template_expr):
    """
    As written here: https://en.wiktionary.org/w/index.php?title=Template:lv-inflection_of&action=edit
    :param template_expr: template instance string with all its parameters
    :return: A malagasy language definition in unicode
    """
    for char in u'{}':
        template_expr = template_expr.replace(char, u'')
    parts = template_expr.split(u'|')
    if len(parts) != 4:
        raise ValueError()

    t_name, lemma, case_name, number_ = parts
    ret = u'%s %s ny teny [[%s]]' % (CASES[case_name], NUMBER[number_], lemma)
    return ret


def parse_latvian_word_forms():
    global last_entry
    last_entry = get_count()
    en_page_processor_class = WiktionaryProcessorFactory.create('en')
    en_page_processor = en_page_processor_class()
    page_output = Output()
    latvian_nouns = pywikibot.Category(pywikibot.Site('en', SITENAME), u'Latvian noun forms')
    counter = 0
    for lv_word_page in latvian_nouns.articles():
        counter += 1
        if last_entry > counter:
            continue
        en_page_processor.process(lv_word_page)
        entries = en_page_processor.getall(definitions_as_is=True)
        entries = [entry for entry in entries if entry[2] == u'lv']
        print entries
        for word, pos, language_code, definition in entries:
            last_entry += 1

            mg_page = pywikibot.Page(pywikibot.Site(SITELANG, SITENAME), word)

            try:
                malagasy_definition = template_expression_to_malagasy_definition(definition)
                lemma = get_lemma(definition)
            except (KeyError, ValueError):
                continue

            # Do not create page if lemma does not exist
            mg_lemma_page = pywikibot.Page(pywikibot.Site(SITELANG, SITENAME), lemma)
            if not mg_lemma_page.exists():
                print 'No lemma :/'
                continue

            mg_entry = Entry(
                entry=word,
                part_of_speech=u'e-ana',
                entry_definition=malagasy_definition,
                language='lv',
            )
            if mg_page.exists():
                new_entry = page_output.wikipage(mg_entry)
                page_content = mg_page.get()
                if page_content.find(u'{{=lv=}}') != -1:
                    if page_content.find(u'{{-e-ana-|lv}}') != -1:
                        continue  # section already exists: No need to go further
                    else:
                        page_content = re.sub(r'==[ ]?{{=lv=}}[ ]?==', new_entry, page_content)
                else:
                    page_content = new_entry + u'\n' + page_content
            else:
                page_content = page_output.wikipage(mg_entry)

            mg_page.put(page_content, u'Teny letôna vaovao')


if __name__ == '__main__':
    try:
        parse_latvian_word_forms()
    except Exception:
        print 'Error occurred'
        save_count()