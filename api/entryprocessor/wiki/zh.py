# coding: utf8


from .base import WiktionaryProcessor


class ZHWiktionaryProcessor(WiktionaryProcessor):
    @property
    def language(self):
        return 'zh'
