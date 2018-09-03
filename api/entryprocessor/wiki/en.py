# coding: utf8

import re

from conf.entryprocessor.languagecodes import LANGUAGE_NAMES
from object_model.word import Entry
from .base import WiktionaryProcessor


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
        for page_entry in self.getall():  # (self.title, pos, self.lang2code(l), defin.strip())
            if page_entry.language == 'en':
                pos = page_entry.part_of_speech
                defin = page_entry.entry_definition
                break

        for entry in re.findall(regex, self.content):
            langcode = entry[0]
            entree = entry[1]

            for x in "();:.,":
                if entry[1].find(x) != -1:
                    continue
            if entry[1].find('|') != -1:
                entree = entree.split("|")[0]

            entry = Entry(
                entry=entree,
                part_of_speech=pos,
                language=langcode,
                entry_definition=defin,
            )
            retcontent.append(entry)

        retcontent.sort()
        # print("Nahitana dikanteny ", len(retcontent))
        return retcontent  # liste( (codelangue, entrée)... )

    def retrieve_etymology(self, content):
        """Maka ny etimolojia rehetra amin'ny teny iray"""

        # Etimolojia manta avy amin'ny fizarana rehetra
        etim = re.findall("===[ ]?Etymology[ ]?[1-9]?===[\n](.*)[\n]+[=]+", content)
        return etim

    def getall(self, definitions_as_is=False):
        items = []
        content = self.content
        content = re.sub("{{l/en\|(.*)}}", "\\1 ", content)  # remove {{l/en}}
        for l in re.findall("[\n]?==[ ]?([A-Za-z]+)[ ]?==\n", content):
            content = content[content.find('==%s==' % l):]
            etimology = self.retrieve_etymology(content)
            etym = etimology[0] if len(etimology) > 0 else ''
            content = re.sub('Etymology', '', content)  # remove etymology section

            # pos
            pos = ''
            ptext = regex_ptext = ''
            for p in self.postran:
                regex_ptext += '%s|' % p

            regex_ptext = regex_ptext.strip('|')

            ptext = '\n={4}[ ]?(%s)[ ]?={4}\n' % regex_ptext
            if re.search(ptext, content) is None:
                ptext = '\n={3}[ ]?(%s)[ ]?={3}\n' % regex_ptext

            posregex = re.findall(ptext, content)

            if not definitions_as_is:
                for regex, replacement in self.regexesrep:
                    c = re.sub(regex, replacement, content)

            # definition
            try:
                defin = content.split('\n#')[1]
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

            if len(defin.strip()) < 1:
                continue

            try:
                language_code = self.lang2code(l)
            except KeyError:
                continue
            else:
                assert self.title is not None
                i = Entry(
                    entry=self.title,
                    part_of_speech=pos,
                    language=language_code,
                    entry_definition=[defin.strip()],
                    etymology=etym
                )
                items.append(i)

        # print("Nahitana dikanteny ", len(items))
        return items
