# coding: utf8
import time
import pywikibot
from urllib import FancyURLopener, urlopen
from lxml import etree
from modules.BJDBmodule import WordDatabase

WORKING_WIKI = pywikibot.Site("mg", "wiktionary")
username = u"%s" % pywikibot.config.usernames['wiktionary']['mg']

TABLE_PATTERN = u"""
{| class=\"wikitable sortable\"
! Kaodim-piteny
! Anarana anglisy
! Isan'ny teny
|-
%s
|}
"""

ROW_PATTERN = u"""
| <tt>[[Endrika:%s|%s]]</tt> || ''%s'' || {{formatnum:%d}}
|-"""


class UnknownLanguageManagerError(Exception):
    pass


class MyOpener(FancyURLopener):
    version = 'Botjagwar/v1.1'


class UnknownlanguageUpdaterBot(object):
    """
    Reads kaodim-piteny tsy fantara subpage and create the categories & templates for new languages
    """
    def __init__(self):
        self.title = u"Mpikambana:%s/Kaodim-piteny fantatra" % username
        self.new_language_page = pywikibot.Page(WORKING_WIKI, self.title)

    def get_new_languages_wikipage(self):
        return self.new_language_page.get()

    def purge_new_languages_wikipage(self):
        """
        Empties the wikipage containing language definitions for future use
        :return:
        """
        try:
            self.new_language_page.put(u"", u"fandiovana")
        except Exception as e:
            print(e)

    def parse_wikipage(self):
        """

        :return:
        """
        text = self.get_new_languages_wikipage()
        language_names = []
        for line in text.split(u"\n"):
            try:
                code, name = line.split(u",")
                code, name = code.strip(), name.strip()
                if len(code) > 3:
                    continue
                language_names.append((code, name))
            except ValueError:
                print (u"Rariteny tsy voaaraka amin'ny andalana")

        return language_names

    @staticmethod
    def put(title, content):
        """

        :param title:
        :param content:
        :return:
        """
        page = pywikibot.Page(WORKING_WIKI, title)
        page.put(content, u"fiteny vaovao")

    def start(self):
        """

        :return:
        """
        print ("UnknownlanguageUpdaterBot")
        parsed_lines = self.parse_wikipage()
        for language_code, language_name in parsed_lines:
            templates_to_be_created = [
                u"Endrika:%s" % language_code,
                u"Endrika:%s/type" % language_code]
            for template in templates_to_be_created:
                self.put(template, language_name)

            self.put(u"Endrika:=%s=" % language_code, language_name.title())

            categories = [
                u"Anarana iombonana",
                u"Mpamaritra anarana",
                u"Matoanteny",
                u"Tambinteny",
                u"Mpampiankin-teny"]
            self.put(u"Sokajy:%s" % language_name, u"[[sokajy:fiteny]]")
            for category in categories:
                page_content = u"[[sokajy:%s]]\n[[sokajy:%s|%s]]" % (
                    language_name, category, language_name[0])
                title = u"Sokajy:%s amin'ny teny %s" % (category, language_name)
                self.put(title, page_content)

        self.purge_new_languages_wikipage()


class UnknownLanguageManagerBot(object):
    """
    Bot script
    """
    def __init__(self):
        database = WordDatabase()
        self.db_conn = database.DB
        self.cursor = self.db_conn.connect.cursor()
        self.lang_list = []

    def get_languages_from_x_days_ago(self, x=30):
        """
        Retrieves languages codes of languages that have been added since x days ago.
        :param x:
        :return:
        """
        query = u"""select distinct(fiteny) as fiteny, count(teny) as isa 
                from data_botjagwar.`teny` 
                where teny.daty 
                    between DATE_SUB(NOW(), INTERVAL %d day) and NOW()
                group by fiteny
                order by fiteny asc;""" % x
        self.cursor.execute(query)
        for language_code, number_of_words in self.cursor.fetchall():
            yield language_code, number_of_words

    def start(self):
        """
        Gets non-existing languages and add them to the wiki page.
        :return:
        """
        print ("UnknownLanguageManagerBot")
        for language_code, number_of_words in self.get_languages_from_x_days_ago():
            language_exists = language_code_exists(language_code)
            if language_exists == 0:
                if len(language_code) == 3:
                    language_name = get_language_name(language_code)
                    self.lang_list.append((language_code, language_name, number_of_words))
            else:
                pass
        self.update_wiki_page()

    def update_wiki_page(self):
        """
        Updates `Lisitry ny kaodim-piteny tsy voafaritra` subpage.
        :return:
        """
        rows = u""
        for code, name, n_words in self.lang_list:
            rows += ROW_PATTERN % (code, code, name, n_words)
        page_content = TABLE_PATTERN % rows
        wikipage = pywikibot.Page(WORKING_WIKI, u"Mpikambana:%s/Lisitry ny kaodim-piteny tsy voafaritra" % username)
        f = open("/tmp/wikipage_save", 'w')
        f.write(page_content.encode('utf8'))
        f.close()
        for i in range(10):
            try:
                wikipage.put(page_content)
                break
            except (pywikibot.PageNotSaved, pywikibot.OtherPageSaveError) as e:
                print (e)
                print (u"Hadisoana, manandrana indray afaka 10 segondra")
                time.sleep(10)


def language_code_exists(language_code):
    """
    Checks whether language code already exists on working wiki
    :param language_code:
    :return:
    """
    page_titles_to_check = [u"Endrika:%s" % language_code,
                            u"Endrika:=%s=" % language_code]
    existence = 0
    for page_title in page_titles_to_check:
        wikipage = pywikibot.Page(WORKING_WIKI, page_title)
        if wikipage.exists() and not wikipage.isRedirectPage():
            existence += 1

    return existence


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
        return u""
    page_xpath = u'//table/tr[2]/td[2]'
    url = u"http://www-01.sil.org/iso639-3/documentation.asp?id=%s" % language_code
    text = urlopen(url).read()
    text = text.decode("utf8")
    tree = etree.HTML(text)
    r = tree.xpath(page_xpath)
    return r[0].text.strip()


if __name__ == '__main__':
    language_updater = UnknownlanguageUpdaterBot()
    language_updater.start()
    unknownl_language_manager = UnknownLanguageManagerBot()
    unknownl_language_manager.start()
