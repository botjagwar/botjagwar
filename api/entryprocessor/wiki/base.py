# coding: utf8
import re
import os

import pywikibot

data_file = os.getcwd() +'/conf/entryprocessor/'

class WiktionaryProcessorException(Exception):
    pass


class WiktionaryProcessor(object):
    """Generic class of all Wiktionary page processors"""

    def __init__(self, test=False, verbose=False):
        self.content = None
        self.Page = None
        self.verbose = verbose
        self.text_set = False

    def process(self, page=None):
        if page is not None:
            assert isinstance(page, pywikibot.Page)
            self.Page = page
        if not self.text_set:
            try:
                if page is None:
                    raise WiktionaryProcessorException("Unable to process: No text has been and 'page' is None")
                self.content = page.get()
            except Exception:
                self.content = ""

    def set_text(self, text):
        self.content = text
        self.text_set = True

    def retrieve_translations(self):
        raise NotImplementedError()

    def getall(self, keepNativeEntries=False):
        raise NotImplementedError()


def stripwikitext(w):
    w = re.sub('[ ]?\[\[(.*)\|(.*)\]\][ ]?', '\\1', w)
    w = w.replace('.', '')
    w = re.sub('[ ]?\{\{(.*)\}\}[ ]?', '', w)
    for c in '[]':
        w = w.replace(c, '')

    return w.strip()


def lang2code(l):
    dictfile = open(data_file + 'languagecodes.dct', 'r')
    f = dictfile.read()
    d = eval(f)
    dictfile.close()

    return d[l]