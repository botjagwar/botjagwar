# coding: utf8
import sys, os


from .base import WiktionaryProcessor

class DEWiktionaryProcessor(WiktionaryProcessor):
    @property
    def language(self):
        return 'de'
