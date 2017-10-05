# coding: utf8

import pywikibot
from __init__ import WiktionaryProcessorFactory
from wiki.base import data_file


class DumpPagegenerator(object):
    def __init__(self, dumpfile, language):
        self.dumpfile = None
        self.list_translations = []
        self.newentries = []
        self.language = language
        self.alltranslations = {}
        self.file = pywikibot.xmlreader.XmlDump(dumpfile)
        self.langblacklist = ['fr', 'en', 'sh', 'de', 'zh']

    def load(self, dumptype, filename, language):
        if dumptype == 'dump':
            self.load_dump(data_file + filename, language)
        elif dumptype == 'titles':
            self.load_titlefile(data_file + filename, language)
            self.process = self.process_titlelist

    def load_dump(self, filename, language='en'):
        self.language = language
        self.file = pywikibot.xmlreader.XmlDump(filename)

    def load_titlefile(self, filename, language='en'):
        self.language = language
        self.file = file(filename, 'r').readlines()

    def get_processed_pages(self):
        wiktionary_processor = WiktionaryProcessorFactory.create(self.language)

        print("getting entry translation")
        for fileentry in self.file.parse():
            wiktionary_processor.process(fileentry.text, fileentry.title)
            yield wiktionary_processor.retrieve_translations()

        print("getting entry page")
        for fileentry in self.file.parse():
            wiktionary_processor.process(fileentry.text, fileentry.title)
            yield wiktionary_processor.getall()
