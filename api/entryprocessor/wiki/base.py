# coding: utf8
import os
import re
from typing import List
from api.config import BotjagwarConfig

data_file = os.getcwd() + '/conf/entryprocessor/'


class WiktionaryProcessorException(Exception):
    pass


class WiktionaryProcessor(object):
    """Generic class of all Wiktionary page processors"""

    @property
    def language(self):
        raise NotImplementedError()

    def __init__(self, test=False, verbose=False):
        self.content = None
        self.Page = None
        self.verbose = verbose

        self.configuration = BotjagwarConfig('wiktionary_processor')
        self.debug = self.configuration.get('debug').lower() == 'true'
        self.text_set = False

    def process(self, page=None):
        if page is not None:
            # assert isinstance(page, pywikibot.Page), self.Page.__class__
            self.Page = page
            self.title = self.Page.title()
        if not self.text_set:
            try:
                if page is None:
                    raise WiktionaryProcessorException(
                        "Unable to process: No text has been and 'page' is None")
                self.content = page.get()
            except SyntaxError as e:
                print(e)
                self.content = ""

    def set_text(self, text):
        self.content = text
        self.text_set = True

    def set_title(self, title):
        self.title = title

    def advanced_extract_definition(self, part_of_speech, definition_line, **other_params):
        return definition_line

    def retrieve_translations(self):
        raise NotImplementedError()

    def get_all_entries(self, keep_native_entries=False, **other_params):
        raise NotImplementedError()

    @staticmethod
    def refine_definition(definition, part_of_speech=None) -> List[str]:
        return [definition]


def stripwikitext(w):
    w = re.sub('[ ]?\\[\\[(.*)\\|(.*)\\]\\][ ]?', '\\1', w)
    w = w.replace('.', '')
    w = re.sub('[ ]?\\{\\{(.*)\\}\\}[ ]?', '', w)
    for c in '[]':
        w = w.replace(c, '')

    return w.strip()


def lang2code(l):
    dictfile = open(data_file + 'languagecodes.dct', 'r')
    f = dictfile.read()
    d = eval(f)
    dictfile.close()

    return d[l]
