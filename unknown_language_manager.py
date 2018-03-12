#!/usr/bin/python3.6
import time

import pywikibot
from lxml import etree

from urllib.request import FancyURLopener, urlopen

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

from database import Base, Word
from modules.decorator import time_this
from datetime import datetime, timedelta

DATABASE_STORAGE_INFO_FILE = 'data/storage_info'
with open(DATABASE_STORAGE_INFO_FILE) as storage_file:
    STORAGE = storage_file.read()

ENGINE = create_engine('sqlite:///%s' % STORAGE)
Base.metadata.create_all(ENGINE)
SessionClass = sessionmaker(bind=ENGINE)

WORKING_WIKI = pywikibot.Site("mg", "wiktionary")
username = "%s" % pywikibot.config.usernames['wiktionary']['mg']

TABLE_PATTERN = """
{| class=\"wikitable sortable\"
! Kaodim-piteny
! Anarana anglisy
! Isan'ny teny
|-
%s
|}
"""

ROW_PATTERN = """
| <tt>[[Endrika:%s|%s]]</tt> || ''%s'' || {{formatnum:%d}}
|-"""


class UnknownLanguageManagerError(Exception):
    pass


class MyOpener(FancyURLopener):
    version = 'Botjagwar/v0.0.2'


class UnknownlanguageUpdaterBot(object):
    """
    Reads kaodim-piteny tsy fantara subpage and create the categories & templates for new languages
    """
    def __init__(self):
        self.title = "Mpikambana:%s/Kaodim-piteny fantatra" % username
        self.new_language_page = pywikibot.Page(WORKING_WIKI, self.title)

    def get_new_languages_wikipage(self):
        return self.new_language_page.get()

    def purge_new_languages_wikipage(self):
        """
        Empties the wikipage containing language definitions for future use
        :return:
        """
        try:
            self.new_language_page.put("", "fandiovana")
        except Exception as e:
            print(e)

    def parse_wikipage(self):
        """
        :return:
        """
        text = self.get_new_languages_wikipage()
        language_names = []
        for line in text.split("\n"):
            try:
                code, name = line.split(",")
                code, name = code.strip(), name.strip()
                if len(code) > 3:
                    continue
                language_names.append((code, name))
            except ValueError:
                print ("Rariteny tsy voaaraka amin'ny andalana")

        return language_names

    def start(self):
        """
        :return:
        """
        print ("UnknownlanguageUpdaterBot")
        parsed_lines = self.parse_wikipage()
        for language_code, language_name in parsed_lines:
            create_category_set(language_code, language_name)
        self.purge_new_languages_wikipage()


class UnknownLanguageManagerBot(object):
    """
    Bot script
    """
    def __init__(self):
        self.lang_list = []
        self.session = SessionClass()

    def __del__(self):
        self.session.close()

    def get_languages_from_x_days_ago(self, x=30):
        """
        Retrieves languages codes of languages that have been added since x days ago.
        :param x:
        :return:
        """
        words = self.session.query(Word.language, func.count(Word.word))\
            .filter(Word.date_changed >= datetime.now() - timedelta(days=x))\
            .group_by(Word.language)

        for language_code, number_of_words in words:
            yield language_code, number_of_words

    def attempt_translations(self):
        """
        :return:
        """
        for language_code, number_of_words in self.get_languages_from_x_days_ago(120):
            language_exists = language_code_exists(language_code)
            if language_exists == 0:
                if len(language_code) == 3:
                    language_name = get_language_name(language_code)
                    try:
                        new_language_name = translate_language_name(language_name)
                        create_category_set(language_code, new_language_name)
                    except (ValueError, pywikibot.exceptions.InvalidTitle):
                        print('Not translatable ', language_name)
                        self.lang_list.append((language_code, language_name, number_of_words))

    def start(self):
        """
        Gets non-existing languages and add them to the wiki page.
        :return:
        """
        print ("UnknownLanguageManagerBot")
        self.attempt_translations()
        self.update_wiki_page()

    def update_wiki_page(self):
        """
        Updates `Lisitry ny kaodim-piteny tsy voafaritra` subpage.
        :return:
        """
        rows = ""
        for code, name, n_words in self.lang_list:
            rows += ROW_PATTERN % (code, code, name, n_words)
        page_content = TABLE_PATTERN % rows
        wikipage = pywikibot.Page(WORKING_WIKI, "Mpikambana:%s/Lisitry ny kaodim-piteny tsy voafaritra" % username)
        f = open("/tmp/wikipage_save", 'w')
        f.write(page_content)
        f.close()
        for i in range(10):
            try:
                wikipage.put(page_content)
                break
            except (pywikibot.PageNotSaved, pywikibot.OtherPageSaveError) as e:
                print (e)
                print ("Hadisoana, manandrana indray afaka 10 segondra")
                time.sleep(10)


@time_this('language_code_exists')
def language_code_exists(language_code):
    """
    Checks whether language code already exists on working wiki
    :param language_code:
    :return:
    """
    print("checking language code '%s'" % language_code)
    page_titles_to_check = ["Endrika:%s" % language_code,
                            "Endrika:=%s=" % language_code]
    existence = 0
    for page_title in page_titles_to_check:
        wikipage = pywikibot.Page(WORKING_WIKI, page_title)
        if wikipage.exists() and not wikipage.isRedirectPage():
            existence += 1

    return existence


@time_this('get_language_name')
def get_language_name(language_code):
    """
    Checks language code length and gets English language name
    :param language_code:
    :return:
    """
    if len(language_code) == 3:
        return get_sil_language_name(language_code)


def get_sil_language_name(language_code):
    """
    gets a page on SIL website to get the language name from the language code
    :param language_code:
    :return:
    """
    if len(language_code) == 2:
        return ""
    page_xpath = '//table/tr[2]/td[2]'
    url = "http://www-01.sil.org/iso639-3/documentation.asp?id=%s" % language_code
    text = urlopen(url).read()
    tree = etree.HTML(text)
    r = tree.xpath(page_xpath)
    return r[0].text.strip()


def translate_language_name(language_name):
    language_name = language_name.lower()
    if len(language_name.split()) > 1 or len(language_name.split('-')) > 1:
        raise ValueError("Can't properly translate this one")
    language_name += '$'

    letter_replacements = [("o", "ô"), ("u", "o"), ('i$', 'y$'), ('y', 'i')]

    cluster_replacements = {
        'ian$': 'ianina$',
        'ese$': 'ey$',
        "cl": "kl",
        "sc": "sk",
        'gue':'ge',
        'gui': 'gi',
        "que": "ke",
        "qui": "ki",
        'oo': 'o',
        'ee': 'i',
        "ch": "ts",
        'ca': 'ka',
        'co': 'kô',
        'cu': 'ko',
        'ce': 'se',
        'ci': 'si',
        'cy': 'si',
        "x": "ks",
    }

    for c, r in letter_replacements:
        language_name = language_name.replace(c, r)

    for c, r in list(cluster_replacements.items()):
        language_name = language_name.replace(c, r)

    return language_name.strip('$')


def create_category_set(language_code, language_name):
    templates_to_be_created = [
        "Endrika:%s" % language_code,
        "Endrika:%s/type" % language_code]
    for template in templates_to_be_created:
        put(template, language_name)

    put("Endrika:=%s=" % language_code, language_name.title())

    categories = [
        "Anarana iombonana",
        "Mpamaritra anarana",
        "Matoanteny",
        "Tambinteny",
        "Mpampiankin-teny"]
    put("Sokajy:%s" % language_name, "[[sokajy:fiteny]]")
    for category in categories:
        page_content = "[[sokajy:%s]]\n[[sokajy:%s|%s]]" % (
            language_name, category, language_name[0])
        title = "Sokajy:%s amin'ny teny %s" % (category, language_name)
        put(title, page_content)


def put(title, content):
    """
    :param title:
    :param content:
    :return:
    """
    page = pywikibot.Page(WORKING_WIKI, title)
    page.put(content, "fiteny vaovao")


if __name__ == '__main__':
    language_updater = UnknownlanguageUpdaterBot()
    language_updater.start()
    unknown_language_manager = UnknownLanguageManagerBot()
    unknown_language_manager.start()

