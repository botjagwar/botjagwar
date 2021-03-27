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
            'Conjunction': 'mpampitohy',
            'Determiner': 'mpam',
            'Idiom': 'fomba fiteny',
            'Phrase': 'fomba fiteny',
            'Proverb': 'ohabolana',
            'Number': 'isa',
            'Noun': 'ana',
            'Adjectival noun': 'mpam',
            'Particle': 'kianteny',
            'Adverb': 'tamb',
            'Root': 'fototeny',
            'Numeral': 'isa',
            'Pronoun': 'solo-ana',
            'Preposition': 'mp.ank-teny',
            'Contraction': 'fanafohezana',
            'Letter': 'litera',
            'Proper noun': 'ana-pr',
            'Prefix': 'tovona',
            'Romanization': 'rômanizasiona',
            'Suffix': 'tovana',
            'Symbol': 'eva',
            'Participle': 'ova-mat',
            'Interjection': 'tenim-piontanana',
            'Infix': 'tsofoka',
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

    def fetch_additional_data(self):


    def getall(self, keepNativeEntries=False, additional_data=False):
        content = self.content
        entries = []
        content = re.sub("{{l/en\|(.*)}}", "\\1 ", content)  # remove {{l/en}}
        for l in re.findall("[\n]?==[ ]?([A-Za-z]+)[ ]?==\n", content):
            pos_level = 3
            try:
                last_language_code = self.lang2code(l)
            except KeyError:
                continue

            last_part_of_speech = None
            definitions = {}
            content = content[content.find('==%s==' % l):]
            lines = content.split('\n')
            for line in lines:
                for en_pos, mg_pos in self.postran.items():
                    if re.match('=' * pos_level + '[ ]?' + en_pos + '[ ]?' + '=' * pos_level, line) is not None:
                        last_part_of_speech = mg_pos

                if line.startswith('# '):
                    defn_line = line
                    defn_line = defn_line.lstrip('# ')
                    if last_part_of_speech is None:
                        continue
                    if last_part_of_speech in definitions:
                        definitions[last_part_of_speech].append(defn_line)
                    else:
                        definitions[last_part_of_speech] = [defn_line]

            for pos, definitions in definitions.items():
                entries.append(
                    Entry(
                        entry=self.title,
                        part_of_speech=pos,
                        language=last_language_code,
                        entry_definition=definitions,
                    )
                )

        return entries

    def retrieve_translations(self):
        regex = re.compile('\{\{t[\+]?\|([A-Za-z]{2,3})\|(.*?)\}\}')
        translations = {}
        entries = []
        content = re.sub("{{l/en\|(.*)}}", "\\1 ", self.content)  # remove {{l/en}}
        for l in re.findall("[\n]?==[ ]?([A-Za-z]+)[ ]?==\n", content):
            last_part_of_speech = None
            content = content[content.find('==%s==' % l):]
            lines = content.split('\n')
            for line in lines:
                for en_pos, mg_pos in self.postran.items():
                    if '===' + en_pos in line:
                        last_part_of_speech = mg_pos

                if len(re.findall(regex, line)) != 0:
                    for language_code, translation in re.findall(regex, line):
                        if last_part_of_speech in translations:
                            translations[last_part_of_speech].append((language_code, translation))
                        else:
                            translations[last_part_of_speech] = [(language_code, translation)]

            for pos, translation_list in translations.items():
                for translation_tuple in translation_list:
                    language, translation = translation_tuple
                    translation = translation[:translation.find('|')] \
                        if translation.find('|') > 0 \
                        else translation
                    entries.append(
                        Entry(
                            entry=translation,
                            part_of_speech=pos,
                            language=language,
                            entry_definition=[self.title],
                        )
                    )

        return entries

