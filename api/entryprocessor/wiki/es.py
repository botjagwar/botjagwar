# coding: utf8

from .base import WiktionaryProcessor


class ESWiktionaryProcessor(WiktionaryProcessor):
    @property
    def language(self):
        return "es"
