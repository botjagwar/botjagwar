# coding: utf8
import time
import pywikibot
from urllib import FancyURLopener, urlopen
from lxml import etree
from modules.BJDBmodule import WordDatabase

WORKING_WIKI = pywikibot.Site("mg", "wiktionary")

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


class UnknownLanguageManager:
    def __init__(self):
        database = WordDatabase()
        self.db_conn = database.DB
        self.cursor = self.db_conn.cursor
        self.lang_list = []

    def get_languages_from_30days_ago(self):
        query = u"""select distinct(fiteny) as fiteny, count(teny) as isa 
                from data_botjagwar.`teny` 
                where teny.daty 
                    between DATE_SUB(NOW(), INTERVAL 30 day) and NOW()
                group by fiteny
                order by fiteny asc;"""
        self.cursor.execute(query)
        for language_code, number_of_words in self.cursor.fetchall():
            yield language_code, number_of_words

    def start(self):
        for language_code, number_of_words in self.get_languages_from_30days_ago():
            language_exists = language_code_exists(language_code)
            if language_exists == 0:
                if len(language_code) == 3:
                    language_name = get_language_name(language_code)
                    self.lang_list.append((language_code, language_name, number_of_words))
            else:
                pass
        self.update_wiki_page()

    def update_wiki_page(self):
        username = u"%s" % pywikibot.config.usernames['wiktionary']['mg']
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
                wikipage.save(page_content)
                break
            except (pywikibot.PageNotSaved, pywikibot.OtherPageSaveError) as e:
                print e
                print u"Hadisoana, manandrana indray afaka 10 segondra"
                time.sleep(10)


def language_code_exists(language_code):
    page_titles_to_check = [u"Endrika:%s" % language_code,
                            u"Endrika:=%s=" % language_code]
    existence = 0
    for page_title in page_titles_to_check:
        wikipage = pywikibot.Page(WORKING_WIKI, page_title)
        if wikipage.exists() and not wikipage.isRedirectPage():
            existence += 1

    return existence


def get_language_name(language_code):
    if len(language_code) == 3:
        return get_sil_language_name(language_code)


def get_sil_language_name(language_code):
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
    bot = UnknownLanguageManager()
    bot.start()
