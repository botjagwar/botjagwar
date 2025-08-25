# coding: utf8
import os
import re
from typing import List


from api.config import BotjagwarConfig

data_file = f"{os.getcwd()}/conf/entryprocessor/"


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

        self.configuration = BotjagwarConfig("wiktionary_processor")
        self.debug = self.configuration.get("debug").lower() == "true"
        self.text_set = False
        self._title = None


    def set_title(self, title):
        """Deprecated, use title property instead."""
        self.title = title

    @property
    def title(self):
        if self.Page is not None:
            return self.Page.title()
        elif self._title is not None:
            return self._title

        return None

    @title.setter
    def title(self, title):
        self._title = title

    def process(self, page=None):
        if page is not None:
            # assert isinstance(page, pywikibot.Page), self.Page.__class__
            self.Page = page
        if not self.text_set:
            try:
                if page is None:
                    raise WiktionaryProcessorException(
                        "Unable to process: No text has been and 'page' is None"
                    )
                self.content = page.get()
            except SyntaxError as e:
                print(e)
                self.content = ""

    def set_text(self, text):
        self.content = text
        self.text_set = True

    def advanced_extract_definition(
        self, part_of_speech, definition_line, **other_params
    ):
        return definition_line

    def retrieve_translations(self):
        raise NotImplementedError()

    def get_all_entries(self, keep_native_entries=False, **other_params):
        raise NotImplementedError()

    @staticmethod
    def refine_definition(definition, part_of_speech=None, **other_params) -> List[str]:
        return [definition]


def stripwikitext(w):
    w = re.sub("[ ]?\\[\\[(.*)\\|(.*)\\]\\][ ]?", "\\1", w)
    w = w.replace(".", "")
    w = re.sub("[ ]?\\{\\{(.*)\\}\\}[ ]?", "", w)
    for c in "[]":
        w = w.replace(c, "")

    return w.strip()


def lang2code(l):
    with open(f"{data_file}languagecodes.dct", "r") as dictfile:
        f = dictfile.read()
        d = eval(f)
    return d[l]
