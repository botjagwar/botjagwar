#!/usr/bin/python3.6
from datetime import datetime, timedelta
import logging
from random import randint
import requests
import time

from lxml import etree
import pywikibot
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func

from api.decorator import time_this
from conf.entryprocessor.languagecodes import LANGUAGE_CODES
from database.dictionary import Word, Base as WordBase
from database.language import Language, Base as LanguageBase

with open('data/language_storage_info') as storage_file:
    language_storage = storage_file.read()
with open('data/word_database_storage_info') as storage_file:
    word_storage = storage_file.read()

log = logging.getLogger(__file__)

word_engine = create_engine('sqlite:///%s' % word_storage)
language_engine = create_engine('sqlite:///%s' % language_storage)
LanguageBase.metadata.create_all(language_engine)
WordBase.metadata.create_all(word_engine)

WordSessionClass = sessionmaker(bind=word_engine)
LanguageSessionClass = sessionmaker(bind=language_engine)
language_session = LanguageSessionClass()
word_session = WordSessionClass()

WORKING_WIKI = pywikibot.Site("mg", "wiktionary")
try:
    username = "%s" % pywikibot.config.usernames['wiktionary']['mg']
except KeyError:
    username = "test"


TABLE_PATTERN = """
{| class=\"wikitable sortable\"
! Kaodim-piteny
! Anarana anglisy
! Isan'ny teny
|-
%s
|}
"""

SIL_CACHE = {}

ROW_PATTERN = """
| <tt>[[Endrika:%s|%s]]</tt> || ''%s'' || {{formatnum:%d}}
|-"""


class UnknownLanguageManagerError(Exception):
    pass


class SilPageException(UnknownLanguageManagerError):
    pass


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
        self.word_session = WordSessionClass()
        self.language_session = LanguageSessionClass()

    def __del__(self):
        self.word_session.close()
        self.language_session.close()

    def get_languages_from_x_days_ago(self, x=30):
        """
        Retrieves languages codes of languages that have been added since x days ago.
        :param x:
        :return:
        """
        words = self.word_session.query(Word.language, func.count(Word.word))\
            .filter(Word.date_changed >= datetime.now() - timedelta(days=x))\
            .group_by(Word.language)

        for language_code, number_of_words in words:
            yield language_code, number_of_words

    def attempt_translations(self):
        """
        :return:
        """
        undocumented_languages = [
            (code, n_words) for (code, n_words) in self.get_languages_from_x_days_ago(120)
            if not is_language_in_base(code)
        ]
        print(undocumented_languages)
        for language_code, number_of_words in undocumented_languages:
            language_exists = language_code_exists(language_code)
            if language_exists == 0:
                if len(language_code) == 3:
                    try:
                        english_language_name = get_language_name(language_code)
                    except Exception as exc:
                        log.error(exc)
                        self.lang_list.append((language_code, '(tsy fantatra)', number_of_words))
                        continue
                    try:
                        malagasy_language_name = translate_language_name(english_language_name)
                        add_language_to_db(language_code, english_language_name, malagasy_language_name)
                        create_category_set(language_code, malagasy_language_name)
                    except (ValueError, pywikibot.exceptions.InvalidTitle):
                        print('Not translatable ', english_language_name)
                        self.lang_list.append((language_code, english_language_name, number_of_words))

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


def add_language_to_db(language_code, english_language_name, malagasy_language_name):
    language = Language(
        iso_code=language_code,
        english_name=english_language_name,
        malagasy_name=malagasy_language_name,
        language_ancestor=None)
    language_session.add(language)
    language_session.commit()
    language_session.flush()


def is_language_in_base(language_code):
    languages = language_session.query(Language).filter(Language.iso_code == language_code).all()
    if len(languages) > 0:
        return True
    else:
        return False


@time_this('language_code_exists')
def language_code_exists(language_code):
    """
    Checks whether language code already exists on working wiki
    :param language_code:
    :return:
    """
    if is_language_in_base(language_code):
        return 1

    print("checking language code '%s'" % language_code)
    page_titles_to_check = ["Endrika:%s" % language_code,
                            "Endrika:=%s=" % language_code]
    existence = 0
    for page_title in page_titles_to_check:
        wikipage = pywikibot.Page(WORKING_WIKI, page_title)
        if wikipage.exists() and not wikipage.isRedirectPage():
            existence += 1
            if '=%s=' % language_code in page_title:
                try:
                    english_name = get_language_name(language_code)
                    malagasy_name = wikipage.get().lower().strip()
                    add_language_to_db(language_code, english_name, malagasy_name)
                except SilPageException:
                    return 0
    return existence


@time_this('get_language_name')
def get_language_name(language_code):
    """
    Checks language code length and gets English language name
    :param language_code:
    :return:
    """
    if language_code in LANGUAGE_CODES:
        print(language_code)
        return LANGUAGE_CODES[language_code]
    elif language_code in SIL_CACHE:
        return SIL_CACHE[language_code]
    else:
        language_name = get_sil_language_name(language_code)
        return language_name


def get_sil_language_name(language_code):
    """
    gets a page on SIL website to get the language name from the language code
    :param language_code:
    :return:
    """
    if len(language_code) == 2:
        return ""

    page_xpath = '//*[@id="node-5381"]/div/div[2]/div/div[1]/span/div/div[2]/div/table/tbody/tr/td[2]'
    url = "https://iso639-3.sil.org/code/%s" % language_code
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:59.0) '
                      'Gecko/20100101 Firefox/59.0'
    }
    time.sleep(randint(1, 20))
    req = requests.get(url, headers=headers)
    if req.status_code != 200:
        raise SilPageException("Error: Status code returned HTTP %d: %s" % (req.status_code, req.text))

    text = req.text
    tree = etree.HTML(text)
    r = tree.xpath(page_xpath)
    if len(r) > 0:
        language = r[0].text.strip()
        SIL_CACHE[language_code] = language
        return language
    else:
        with open('/tmp/error.html', 'w') as f:
            f.write(text)
        raise SilPageException('Error')


def translate_language_name(language_name):
    language_name = language_name.lower()
    if len(language_name.split()) > 1 or len(language_name.split('-')) > 1:
        raise ValueError("Can't properly translate this one")

    language_name += '$'
    letter_replacements = [("o", "ô"), ("u", "o"), ('y', 'i'), ('i$', 'y$')]
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

    language_name = language_name.strip('$')
    return language_name


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
