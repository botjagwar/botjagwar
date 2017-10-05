# coding: utf8


class WiktionaryProcessor(object):
    """Generic class of all Wiktionary page processors"""

    def __init__(self, test=False, verbose=False):
        self.content = None
        self.Page = None
        self.verbose = verbose
        self.text_set = False

    def process(self, page):
        self.Page = page
        if not self.text_set:
            try:
                self.content = page.get()
            except Exception:
                self.content = u""

    def set_text(self, text):
        self.content = text
        self.text_set = True

    def retrieve_translations(self, page_c):
        raise NotImplementedError()

    def getall(self, keepNativeEntries=False):
        raise NotImplementedError()
