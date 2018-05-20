# coding: utf8

import re
import pywikibot
from .base import WiktionaryProcessor
from conf.entryprocessor.languagecodes import LANGUAGE_NAMES


class ENWiktionaryProcessor(WiktionaryProcessor):
    def __init__(self, test=False, verbose=False):
        super(ENWiktionaryProcessor, self).__init__(test=test, verbose=verbose)
        self.verbose = True
        self.text_set = False
        self.test = test
        self.postran = {
            'Verb': 'mat',
            'Adjective': 'mpam',
            'Noun': 'ana',
            'Adverb': 'tamb',
            'Pronoun': 'solo-ana',
            'Prefix': 'tovona',
            'Suffix': 'tovana'
        }
        self.regexesrep = [
            (r'\{\{l\|en\|(.*)\}\}', '\\1'),
            (r'\{\{vern\|(.*)\}\}', '\\1'),
            (r"\[\[(.*)#(.*)\|?[.*]?\]?\]?", "\\1"),
            (r"\{\{(.*)\}\}", ""),
            (r'\[\[(.*)\|(.*)\]\]', '\\1'),
            (r"\((.*)\)", "")]

        self.verbose = verbose

        self.code = LANGUAGE_NAMES

    def lang2code(self, l):
        return self.code[l]

    def retrieve_translations(self):
        """Maka ny dikanteny ao amin'ny pejy iray"""
        retcontent = []
        regex = '\{\{t[\+\-]+?\|([A-Za-z]{2,3})\|(.*?)\}\}'
        pos = 'ana'
        defin = ""
        for allentrys in self.getall():  # (self.title, pos, self.lang2code(l), defin.strip())
            if allentrys[2] == 'en':
                pos = allentrys[1]
                defin = allentrys[3]
                break

        for entry in re.findall(regex, self.content):
            langcode = entry[0]
            entree = entry[1]
            try:
                entree = str(entry[1])
            except UnicodeDecodeError:
                entree = str(entry[1], 'latin1')

            for x in "();:.,":
                if entry[1].find(x) != -1:
                    continue
            if entry[1].find('|') != -1:
                entree = entree.split("|")[0]

            e = (entree, pos, langcode, defin.strip())  # (
            retcontent.append(e)
        try:
            retcontent.sort()
        except UnicodeError:
            pass
        # print("Nahitana dikanteny ", len(retcontent))
        return retcontent  # liste( (codelangue, entrée)... )

    def retrieve_etymologies(self):
        """Maka ny etimolojia rehetra amin'ny teny iray"""

        # Etimolojia manta avy amin'ny fizarana rehetra
        etim = re.findall("===[ ]?Etymology[ ]?[1-9]?===[\n](.*)[\n]+[=]+", self.content)
        print(etim)
        return etim

    def getall(self, definitions_as_is=False):
        items = []
        c = self.content
        c = re.sub('Etymology', '', c)  # famafana ny etimilojia
        c = re.sub("\{\{l\/en\|(.*)\}\}", "\\1 ", c)  # fanovana ny endrika {{l/en}}
        for l in re.findall("[\n]?==[ ]?([A-Za-z]+)[ ]?==\n", c):
            c = c[c.find('==%s==' % l):]

            # pos
            pos = ''
            ptext = regex_ptext = ''
            for p in self.postran:
                regex_ptext += '%s|' % p
            regex_ptext = regex_ptext.strip('|')

            ptext = '\n={4}[ ]?(%s)[ ]?={4}\n' % regex_ptext
            if re.search(ptext, c) is None:
                ptext = '\n={3}[ ]?(%s)[ ]?={3}\n' % regex_ptext
            posregex = re.findall(ptext, c)

            if not definitions_as_is:
                for regex, replacement in self.regexesrep:
                    c = re.sub(regex, replacement, c)

            # definition
            try:
                defin = c.split('\n#')[1]

                if defin.find('\n') != -1:
                    defin = defin[:defin.find('\n')]
            except IndexError:
                if self.verbose: print("Hadisoana indexerror.")
                continue

            if not definitions_as_is:
                for regex, replacement in self.regexesrep:
                    defin = re.sub(regex, replacement, defin).strip()

                for char in '{}':
                    defin = defin.replace(char, '')

            for char in '[]':
                defin = defin.replace(char, '')

            defins = defin.split(',')
            if len(defins) > 1:
                defin = defins[0]

            # print(ptext)
            for p in posregex:
                if p not in self.postran:
                    if self.verbose: print("Tsy ao amin'ny lisitry ny karazanteny fantatra ilay teny")
                    continue
                else:
                    pos = p
                    break
            try:
                pos = self.postran[pos]
            except KeyError:
                if self.verbose: print(("Tsy nahitana dikan'ny karazan-teny %s" % pos))
                continue
            if defin.startswith('to ') or defin.startswith('To '):
                pos = 'mat'
                defin = defin[2:]
            elif defin.startswith('a ') or defin.startswith('A '):
                pos = 'ana'
                defin = defin[1:]
            if len(defin.strip()) < 1: continue
            # FIXME: return an object instead of a tuple
            try:
                i = (self.Page.title(),
                     pos,
                     self.lang2code(l),
                     defin.strip())  # (
                if self.verbose: pywikibot.output('%s --> teny  "%s" ; famaritana: %s' % i)
                items.append(i)
            except KeyError:
                continue

        # print("Nahitana dikanteny ", len(items))
        return items