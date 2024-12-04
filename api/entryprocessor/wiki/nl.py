# coding: utf8


from .base import WiktionaryProcessor


class NLWiktionaryProcessor(WiktionaryProcessor):
    @property
    def language(self):
        return "nl"
