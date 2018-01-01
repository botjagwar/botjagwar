# coding: utf8

import re
from base import WiktionaryProcessor
from base import stripwikitext


class MGWiktionaryProcessor(WiktionaryProcessor):
    def __init__(self, test=False, verbose=False):
        self.content = None

    def retrieve_translations(self, page_c):  # Needs updating
        """Fampirimana ny dikanteny azo amin'ny alalan'ny REGEX araka ny laharan'ny Abidy"""
        ret = []
        if page_c.find('{{}} :') == -1:
            return ret
        trads = re.findall("# (.*) : \[\[(.*)\]\]", page_c)
        trads.sort()
        tran = re.sub("# (.*) : \[\[(.*)\]\]", '', page_c)
        tran = tran.strip('\n')
        trstr = '{{}} :'
        tran = tran.replace('{{}} :', '')
        if len(trads) > 200:
            return tran
        for i in trads:
            trstr = trstr.replace("{{}} :", "# %s : [[%s]]\n{{}} :" % i)
            ret.append(i)

        return ret

    def getall(self, keep_native_entries=False):
        items = []
        for lang in re.findall('\{\{\-([a-z]{3,7})\-\|([a-z]{2,3})\}\}', self.content):
            # word DEFINITION Retrieving
            d1 = self.content.find("{{-%s-|%s}}" % lang) + len("{{-%s-|%s}}" % lang)
            d2 = self.content.find("=={{=", d1) + 1 or self.content.find("== {{=", d1) + 1
            if d2:
                definition = self.content[d1:d2]
            else:
                definition = self.content[d1:]
            try:
                definition = definition.split('\n# ')[1]
            except IndexError:
                # print(" Hadisoana : Tsy nahitana famaritana")
                continue
            if definition.find('\n') + 1:
                definition = definition[:definition.find('\n')]
                definition = re.sub("\[\[(.*)#(.*)\|?\]?\]?", "\\1", definition)
            definition = stripwikitext(definition)
            if not definition:
                continue

            else:
                i = (lang[0].strip(),  # POS
                     lang[1].strip(),  # lang
                     definition)
                items.append(i)
                # pywikibot.output(u" %s --> %s : %s"%i)
        # print("Nahitana dikanteny ", len(items) ", len(items))
        return items
