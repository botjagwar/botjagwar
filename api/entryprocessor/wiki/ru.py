# coding: utf8


from .base import WiktionaryProcessor


class RUWiktionaryProcessor(WiktionaryProcessor):
    @property
    def language(self):
        return 'ru'
