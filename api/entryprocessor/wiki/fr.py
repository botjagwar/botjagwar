# coding: utf8

import re

import pywikibot

from object_model.word import Entry
from .base import WiktionaryProcessor
from .base import stripwikitext


class FRWiktionaryProcessor(WiktionaryProcessor):
    def __init__(self, test=False, verbose=False):
        super(FRWiktionaryProcessor, self).__init__(test=test, verbose=verbose)
        self.verbose = verbose
        self.text_set = False
        self.content = None
        self.postran = {
            'verbe': 'mat',
            'adjectif': 'mpam',
            'nom': 'ana',
            'adverbe': 'tamb',
            'pronom': 'solo-ana',
            'préfixe': 'tovona',
            'suffixe': 'tovana'
        }

    def retrieve_translations(self):
        retcontent = []
        regex = r'\{\{trad[\+\-]+?\|([A-Za-z]{2,3})\|(.*?)\}\}'
        part_of_speech = 'ana'
        definition = ""
        for entry in self.getall():
            print(entry)
            if entry.language == 'fr':
                if entry.part_of_speech in self.postran:
                    part_of_speech = self.postran[entry.part_of_speech]
                definition = entry.entry
                break

        for entry in re.findall(regex, self.content):
            langcode = entry[0]
            entree = str(entry[1])

            for x in "();:.,":
                if entry[1].find(x) != -1:
                    continue
            if entry[1].find('|') != -1:
                entree = entree.split("|")[0]

            if part_of_speech in self.postran:
                part_of_speech = self.postran[part_of_speech]

            e = Entry(
                entry=entree,
                part_of_speech=part_of_speech,
                language=langcode,
                entry_definition=[definition.strip()]
            )
            retcontent.append(e)
        try:
            retcontent.sort()
        except UnicodeError:
            pass

        return retcontent

    def getall(self, keepNativeEntries=False):
        """languges sections in a given page formatting: [(POS, lang, definition), ...]"""
        if self.Page is not None:
            assert isinstance(self.Page, pywikibot.Page), self.Page.__class__
        items = []

        if self.content is None:
            raise Exception("self.page tsy voafaritra. self.process() tsy mbola nantsoina")

        ct_content = self.content
        for lang in re.findall(
                '{{S\|([a-z]+)\|([a-z]{2,3})',
                self.content):
            # print(ct_content)
            # word DEFINITION Retrieving
            d1 = ct_content.find("{{S|%s|%s" % lang)
            d2 = ct_content.find("=={{langue|", d1) + 1
            if not d2:
                d2 = ct_content.find("== {{langue|", d1 + 50) + 1
            d_ptr = ct_content.find("=={{langue|%s" % lang[1], d1) + 1
            if not d_ptr:
                d_ptr = ct_content.find("== {{langue|%s" % lang[1], d1) + 1

            if d2 > d1:
                definition = ct_content[d1:d2]
            else:
                definition = ct_content[d1:]
            try:
                definition = definition.split('\n# ')[1]
                definition = re.sub("\[\[(.*)#(.*)\|?[.*]?\]?\]?", "\\1", definition)
            except IndexError:
                ct_content = ct_content[d_ptr:]
                continue

            ct_content = ct_content[d_ptr:]
            if definition.find('\n') + 1:
                definition = definition[:definition.find('\n')]

            definition = stripwikitext(definition)
            if not definition:
                ct_content = ct_content[d_ptr:]
                continue

            pos = frpos = lang[0].strip()  # POS
            if frpos in self.postran:
                pos = self.postran[frpos]

            i = Entry(
                entry=self.title,
                part_of_speech=pos,
                language=lang[1].strip(),
                entry_definition=[definition.strip()]
            )

            items.append(i)

        # print("Nahitana dikanteny ", len(items))
        return items
