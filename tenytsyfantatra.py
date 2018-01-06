# coding: utf8
import pywikibot
import os
import re, time
from modules.database import Database
from modules.database.word import WordDatabase
from modules.decorator import time_this
from _mysql_exceptions import DataError, IntegrityError

WORKING_WIKI = pywikibot.getSite('mg', 'wiktionary')
username = u"%s" % pywikibot.config.usernames['wiktionary']['mg']
mt_data_file = os.getcwd() + '/user_data/dikantenyvaovao/'


class UnknownWordManagerError(Exception):
    pass


class UnknownWordManagerBot(object):
    def __init__(self):
        self.unknown_words_file = open(mt_data_file + "word_hits", "r")
        self.standard_line_regex = re.compile(r"(.*)[ ]\[([a-zA-Z]+)\]")
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
        self.translation_tables = {
            'en': Database(table="anglisy_malagasy"),
            'fr': Database(table="frantsay_malagasy")
        }

    def __del__(self):
        """
        Properly close all database connections.
        Returns:

        """
        self.word_db.close()
        self.unknown_words_file.close()
        for _, database in self.dictionary_tables:
            del database
        for _, database in self.translation_views:
            del database
        for _, database in self.translation_tables:
            del database

    def _get_word_id(self, word, language):
        """
        Gets the word ID
        :param word: word
        :param language: language the word belongs to
        :return: the word ID
        """
        result = self.dictionary_tables[language].read({
            self.language[language] : word
        }, select="%s_wID" % language)
        return result[0]

    def insert_words_from_file(self, file_name):
        """
        Inserts all the words from a given file whose format is
        :param file_name: name of the file
        :return:
        """
        f = open(mt_data_file + file_name, "r")
        for line in f.readlines():
            line = line.decode('utf8')
            line = line.strip(u'\n')
            try:
                word, language, hits, translation = line.split(u":")
                if translation == u'':
                    continue

                # insert the word
                wid = self._get_word_id(word, language)[0]
                # print wid, translation, len(translation)
                try:
                    self.translation_tables[language].insert({
                        u"%s_wID" % language : str(wid),
                        u"mg" : translation})
                except (DataError, IntegrityError):
                    pass
            except ValueError:  # too many values to unpack
                pass

    @time_this(u'aggregator')
    def get_unknown_words_from_file(self):
        """
        Reads word_hits file. Copares it to the translation table in database
        
        Returns: an aggregated list of unknown words containing the word and the number of hits for that word
        """
        counter = 0
        t = time.time()
        pre_aggregate = {}
        print u'PREAGGREGATE DATA'
        for line in self.unknown_words_file.readlines():
            counter += 1
            if (counter % 1000) == 0:
                dt = time.time() - t
                print counter, u"lines treated; ", len(pre_aggregate), \
                    u"aggregated.", u"(%f wps)" % (100./dt)
                t = time.time()

            line = line.decode('utf8')
            elements = self.standard_line_regex.search(line).groups()
            translation, language_code = elements

            if (translation, language_code) in pre_aggregate:
                pre_aggregate[(translation, language_code)] += 1
            else:
                pre_aggregate[(translation, language_code)] = 1

        counter = 0
        print u'QUERYING DATABASE ON PREAGGREGATED DATA'
        # Lightning fast search (100x speedup compared to database select!)
        words = {
            'en': set([unicode(w, 'latin1') for _, _, w in self.dictionary_tables['en'].read_all()]),
            'fr': set([unicode(w, 'latin1') for _, _, w in self.dictionary_tables['fr'].read_all()])
        }
        for word_and_language, hits in pre_aggregate.items():
            counter += 1
            if (counter % 100) == 0:
                dt = time.time() - t
                print counter, u"lines treated; ", len(self.aggregated_unknown_words), \
                    u"aggregated.", u"(%f wps)" % (100. / dt)
                t = time.time()
            translation, language_code = word_and_language

            if translation in words[language_code]:
                if (translation, language_code) not in self.aggregated_unknown_words:
                    self.aggregated_unknown_words[(translation, language_code)] = hits

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
                    print (u"Left part of '=' could not match expected standard line format. Skipping.")
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


@time_this(u"AGGREGATED WORDS")
def aggregate_words():
    """
    Parses the list of unknown words and writes a file containing a sorted list of all pivot words
    with the language they belong to and the number of times they've been used, in colon-separated values.
    :return:
    """
    bot = UnknownWordManagerBot()
    unknowns = bot.get_unknown_words_from_file()
    save_aggregated_in_file(unknowns)
    save_aggregated_on_wiki(unknowns)


def save_aggregated_on_wiki(unknowns):
    elems = unknowns.items()
    sorted_by_hits = [(hits, entry) for entry, hits in elems]
    sorted_by_hits.sort()
    sorted_by_hits = sorted_by_hits[::-1]
    sorted_by_hits = sorted_by_hits[:10000]

    # Generating wikitext
    wikitext = u""
    for hits, entry in sorted_by_hits:
        word, language = entry
        wikitext += u"[[%s]] (%s, %d), \n" % (word, language, hits)

    # keeping a local copy
    f = open(u'/tmp/lisitry ny teny tsy fantatra', 'w')
    f.write(wikitext.encode('utf8'))
    f.close()

    # Saving page on-wiki
    page = pywikibot.Page(WORKING_WIKI, u'Mpikambana:%s/Lisitry ny teny tsy fantatra' % username)
    page.put(wikitext, u'Teny tsy fantatra vaovao')


def save_aggregated_in_file(unknowns):
    f = open(mt_data_file + u'unknown_words', "w")
    elems = unknowns.keys()
    elems.sort()
    for e in elems:
        hits = unknowns[e]
        s = u"%s:%s:%d:\n" % (e[0], e[1], hits)
        f.write(s.encode('utf8'))

    f.close()


def insert_words():
    bot = UnknownWordManagerBot()
    bot.insert_words_from_file('translated_unknown_words')


if __name__ == '__main__':
    aggregate_words()
    #insert_words()