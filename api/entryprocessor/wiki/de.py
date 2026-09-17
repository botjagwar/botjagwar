# coding: utf8


from .base import WiktionaryProcessor


class DEWiktionaryProcessor(WiktionaryProcessor):
    @property
    def language(self):
        return "de"
