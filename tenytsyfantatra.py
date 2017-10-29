# coding: utf8

import pywikibot
import os
import re
from modules.BJDBmodule import Database
from modules.BJDBmodule import WordDatabase

WORKING_WIKI = pywikibot.getSite('mg', 'wiktionary')
username = u"%s" % pywikibot.config.usernames['wiktionary']['mg']
mt_data_file = os.getcwd() + '/user_data/dikantenyvaovao/'


class UnknownWordManagerError(Exception):
    pass


class UnknownWordManagerBot(object):
    def __init__(self):
        self.unknown_words_file = open(mt_data_file + "word_hits", "r")
        self.standard_line_regex = re.compile("(.*)[ ]\[([a-zA-Z]+)\]")
        self.word_db = WordDatabase()
        self.aggregated_unknown_words = {}
        self.language = {
            'en': 'anglisy',
            'fr': 'frantsay',
        }
        self.dictionary_databases = {
            'en': Database(table="anglisy"),
            'fr': Database(table="frantsay")
        }
        self.translation_databases = {
            'en': Database(table="anglisy_malagasy"),
            'fr': Database(table="frantsay_malagasy")
        }

    def __del__(self):
        self.word_db.close()
        self.unknown_words_file.close()
        for language, database in self.dictionary_databases:
            database.close()
        for language, database in self.translation_databases:
            database.close()

    def get_unknown_words_from_file(self):
        for line in self.unknown_words_file.readlines():
            translation, language_code = self.standard_line_regex.search(line).group()
            tr = self.word_db.translate(translation, language_code)
            if not tr:
                if (translation, language_code) not in self.aggregated_unknown_words:
                    self.aggregated_unknown_words[(translation, language_code)] = 1
                else:
                    self.aggregated_unknown_words[(translation, language_code)] += 1

        return self.aggregated_unknown_words

    def parse_unknown_words_from_wikipage_content(self, content):
        for line in content.split(u"# "):
            line = line.strip(u"\n")
            if u"=" in line:
                std_line, mg_translation = line.split(u"=")
                try:
                    word, language = self.standard_line_regex.search(std_line).group()
                except AttributeError:
                    print ("Left part of '=' could not match expected standard line format. Skipping.")
                else:
                    # update database using translation;
                    response = self.dictionary_databases[language].read({
                        self.language[language]: word}, u"%d_wID" % language)
                    en_wid = response[0][0]
                    data = {
                        u"en_wID": en_wid,
                        u"mg": mg_translation,
                    }
                    self.translation_databases[language].insert(data)
                    # delete from aggregated_unknown_words
                    if (word, language) in self.aggregated_unknown_words:
                        del self.aggregated_unknown_words[(word, language)]


class UnknownWordUpdaterBot(object):
    def __init__(self):
        self.title = u"Mpikambana:%s/Teny tsy fantatra" % username
        self.unknown_words_page = pywikibot.Page(
            WORKING_WIKI, self.title)

    def __del__(self):
        pass

    def get_translations_from_wiki(self):
        pass
