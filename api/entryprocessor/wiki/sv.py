# coding: utf8

from .base import WiktionaryProcessor


class SVWiktionaryProcessor(WiktionaryProcessor):
    @property
    def language(self):
        return 'sv'
