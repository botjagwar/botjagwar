# coding: utf8

import re
import pywikibot
from base import WiktionaryProcessor
from base import stripwikitext


class FRWiktionaryProcessor(WiktionaryProcessor):
    def __init__(self, test=False, verbose=False):
        self.verbose = verbose
        self.text_set = False
        self.content = None
        self.postran = {
            u'verbe': 'mat',
            u'adjectif': 'mpam',
            u'nom': 'ana',
            u'adverbe': 'tamb',
            u'pronom': 'solo-ana',
            u'préfixe': 'tovona',
            u'suffixe': 'tovana'
        }

    def retrieve_translations(self):
        retcontent = []
        regex = '\{\{trad[\+\-]+?\|([A-Za-z]{2,3})\|(.*?)\}\}'
        pos = 'ana'
        defin = u""
        for allentrys in self.getall():  # (self.title, pos, self.lang2code(l), defin.strip())
            if allentrys[2] == 'fr':
                pos = allentrys[1]
                if self.postran.has_key(pos):
                    pos = self.postran[pos]
                defin = allentrys[3]
                break

        for entry in re.findall(regex, self.content):
            langcode = entry[0]
            try:
                entree = unicode(entry[1])
            except UnicodeDecodeError:
                entree = unicode(entry[1], 'latin1')

            for x in "();:.,":
                if entry[1].find(x) != -1:
                    continue
            if entry[1].find('|') != -1:
                entree = entree.split("|")[0]

            if self.postran.has_key(pos):
                pos = self.postran[allentrys[1]]
            e = (entree, pos, langcode, defin.strip())  # (
            retcontent.append(e)
        try:
            retcontent.sort()
        except UnicodeError:
            pass

        return retcontent

    def getall(self, keepNativeEntries=False):
        """languges sections in a given page formatting: [(POS, lang, definition), ...]"""
        assert type(self.Page) is pywikibot.Page
        items = []

        if self.content is None:
            raise Exception("self.page tsy voafaritra. self.process() tsy mbola nantsoina")

        ct_content = self.content
        for lang in re.findall(
                '\{\{S\|([a-z]+)\|([a-z]{2,3})',
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
                print(" Hadisoana : Tsy nahitana famaritana")
                ct_content = ct_content[d_ptr:]
                continue

            ct_content = ct_content[d_ptr:]
            if definition.find('\n') + 1:
                definition = definition[:definition.find('\n')]

            definition = stripwikitext(definition)
            if not definition:
                ct_content = ct_content[d_ptr:]
                continue

            if lang[1].strip() == 'fr':
                pass
            else:
                pos = frpos = lang[0].strip()  # POS
                if self.postran.has_key(frpos):
                    pos = self.postran[frpos]

                i = (self.Page.title(),
                     pos,  # POS
                     lang[1].strip(),  # lang
                     definition)
                items.append(i)
                # pywikibot.output(u" %s --> %s : %s"%i)
        # print("Nahitana dikanteny ", len(items))
        return items
