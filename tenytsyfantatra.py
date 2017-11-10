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
        self.dictionary_tables = {
            'en': Database(table="anglisy"),
            'fr': Database(table="frantsay")
        }
        self.translation_views = {
            'en': Database(table="en_mg"),
            'fr': Database(table="fr_mg")
        }

    def __del__(self):
        """
        Properly close all database connections.
        Returns:

        """
        self.word_db.close()
        self.unknown_words_file.close()
        for language, database in self.dictionary_tables:
            del database
        for language, database in self.translation_views:
            del database

    def get_unknown_words_from_file(self):
        """
        Reads word_hits file. Copares it to the translation table in database
        
        Returns: an aggregated list of unknown words containing the word and the number of hits for that word
        """
        for line in self.unknown_words_file.readlines():
            elements = self.standard_line_regex.search(line).groups()
            translation, language_code = elements
            word_exists = self.dictionary_tables[language_code].read(
                {self.language[language_code]: translation},
                select=self.language[language_code])
            if word_exists:
                if (translation, language_code) not in self.aggregated_unknown_words:
                    self.aggregated_unknown_words[(translation, language_code)] = 1
                else:
                    self.aggregated_unknown_words[(translation, language_code)] += 1

        return self.aggregated_unknown_words

    def put_unknown_words(self, wikipage):
        """
        Saves to the wikipage the aggregated list of unknown words
        Args:
            wikipage: pywikibot.Page instance
                    
        Raises: UnknownWordManagerError if wikipage is not an instance of pywikibot.Page

        """
        if not isinstance(wikipage, pywikibot.Page):
            raise UnknownWordManagerError()
        content = u""
        for unknown_word, language_code in sorted(self.aggregated_unknown_words):
            content += u"# %s" % unknown_word
        wikipage.put(content, u"manavao ny lisitry ny teny tsy fantatra")

    def parse_unknown_words_from_wikipage_content(self, wikipage):
        """
        Gets from the wikipage the list of unknown words. Those who have been translated will be removed
        and the provided translation will be uploaded to the database.
        Args:
            wikipage: pywikibot.Page instance

        Returns:

        """
        if not isinstance(wikipage, pywikibot.Page):
            raise UnknownWordManagerError()
        content = wikipage.get()
        for line in content.split(u"# "):
            line = line.strip(u"\n")
            if u"=" in line:
                std_line, mg_translation = line.split(u"=")
                try:
                    word, language = self.standard_line_regex.search(std_line).groups()
                except AttributeError:
                    print ("Left part of '=' could not match expected standard line format. Skipping.")
                else:
                    # update database using translation;
                    response = self.dictionary_tables[language].read({
                        self.language[language]: word}, u"%d_wID" % language)
                    en_wid = response[0][0]
                    data = {
                        u"en_wID": en_wid,
                        u"mg": mg_translation,
                    }
                    self.translation_views[language].insert(data)
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


if __name__ == '__main__':
    bot = UnknownWordManagerBot()
    unknowns = bot.get_unknown_words_from_file()
    print (unknowns)
