# -*- coding: utf8 -*-
import time
import re
import sys
import os
import random
import threading
import signal
import traceback

import pywikibot as pwbot

from modules import BJDBmodule, ircbot
from modules.translation.core import Translation, TranslationsHandler
from modules.translation.analysis import (analyse_edit_hours, analyse_translations,
                                          MissingTranslations, Translations_per_day_hour)
from modules.translation.test import testTranslate
import list_wikis

# GLOBAL VARS
verbose = False
nwikimax = 15
databases = []
data_file = 'conf/dikantenyvaovao/'


def doexit(*args, **kwargs):
    time.sleep(1500000)
    if len(databases) > 0:
        for db in databases:
            db.close()
    os.kill(os.getpid(), signal.SIGTERM)


def irc_retrieve(channel=''):
    set_throttle(1)
    x = threading.Thread(target=doexit)
    x.daemon = True
    x.start()

    missing_translations = MissingTranslations(data_file)
    if not len(channel):
        channel = 'en'
    bot = IRC_RC_Bot(channel)
    while 1:
        try:
            bot.start()
        except KeyError:
            time.sleep(10)
            continue
        except KeyboardInterrupt:
            missing_translations.update()
            bot.die()
            return


# Throttle Config
def set_throttle(i):
    from pywikibot import throttle
    t = throttle.Throttle(pwbot.Site('mg', 'wiktionary'), mindelay=0, maxdelay=1)
    pwbot.config2.put_throttle = 1
    t.setDelays(i)


def add_translations(last_x_hours=1):
    """Add translations to the destination language entry
    @last_x_hours all translations added in the last hour
    """
    last_x_hours = int(last_x_hours)
    currt_time = time.time()
    x_hours_ago = time.gmtime(currt_time - last_x_hours * 3600)

    database = BJDBmodule.WordDatabase()
    databases.append(database)
    translation_handler = TranslationsHandler()

    # maka ny dikanteny hita hatry ny ora voalaza
    q = "select * from `%(DB)s`.`%(table)s` where " % database.DB.infos
    q += "`daty` >= '%04d-%02d-%02d %02d:%02d:%02d'" % tuple(x_hours_ago)[:6]

    allwords = database.DB.raw_query(q)
    mg_words = {}
    count = 0
    for word in allwords:
        count += 1
        if not count % 10000: print count
        for mgtranslation in word[3].split(','):
            mgtranslation = mgtranslation.strip()
            for char in '[]':
                mgtranslation = mgtranslation.replace(char, '')
            try:
                mg_words[mgtranslation].append((word[5], word[1]))
            except KeyError:
                mg_words[mgtranslation] = []
                mg_words[mgtranslation].append((word[5], word[1]))
    print count
    count = 0
    print "lanjan'ny diksionera : ", len(mg_words)

    for mgword in mg_words:
        # print mg_words[mgword]

        mg_page = pwbot.Page(pwbot.Site('mg', "wiktionary"), mgword.decode('latin1'))
        page_c = u""

        try:
            page_c = orig = mgPage.get()
            print "original length:", len(page_c)
        except Exception:
            continue

        ftranslationlist = set(mg_words[mgword])
        ftranslationlist = list(ftranslationlist)
        translation_handler.setcontent(page_c)
        page_c = translation_handler.add(ftranslationlist)

        pwbot.output(">>> %s <<<" % mg_page.title())
        print "output length:", len(page_c)
        page_c = page_c.replace("\n]", "")
        pwbot.showDiff(orig, page_c)
        while 1:
            try:
                # pwbot.output(page_c)
                mg_page.put_async(page_c, "+dikanteny")
                break
            except pwbot.exceptions.PageNotSaved:
                print "Tsy nahatahiry ilay pejy... manandrana"
                time.sleep(10)

        count += 1


class IRC_RC_Bot(ircbot.SingleServerIRCBot):
    """IRC client used to track edits on targetted wikis.
    @lang string containing languages of editions to track.
    For example : fr,en,de will track fr.wiktionary, en.wiktionary and de.wiktionary
    @user the username which will be use by the IRC client
    """

    def __init__(self, lang, user="botjagwar-w%x" % random.randint(1, 0xffff)):
        self.channels_list = []
        self.chronometer = 0.0
        self.change_langs(lang)
        self.errfile = file(data_file + 'dikantenyvaovao.exceptions', 'a')
        self.iso2languagename = {}
        self.joined = []
        self.langs = []
        self.stats = {'edits': 0.0, 'newentries': 0.0, 'errors': 0.0}
        self.translations = Translation(data_file)
        self.tran_per_hour = Translations_per_day_hour(data_file)
        self.username = user

        self.connect_in_languages()

    def change_langs(self, langstring):
        self.langs = re.split("\,[ ]?", langstring)

    def connect_in_languages(self):
        """mametaka fitohizana amin'ny tsanely irc an'i Wikimedia"""
        print "\n---------------------\n       PARAMETATRA : "
        lister = list_wikis.Wikilister()
        self.langs = lister.getLangs("wiktionary")
        i = 0
        for language in self.langs:
            if i > nwikimax:
                break
            i += 1
            if language == 'mg':
                continue
            language = language.strip()
            channel = "#%s.wiktionary" % language
            print "kaodim-piteny:", language, ", tsanely:", channel, " anarana:", self.username

            irc_bot = ircbot.SingleServerIRCBot.__init__(
                self, [("irc.wikimedia.org", 6667)], self.username, "Bot-Jagwar [IRCbot v2].")
            self.joined.append(language)
            self.channels_list.append(irc_bot)
        print "Vita ny fampitohizana"

    def on_welcome(self, serv, ev):
        for language in self.joined:
            # print "Mangataka tonga soa avy amin'i #"+language+".wiktionary"
            serv.join("#" + language + ".wiktionary")

    def on_kick(self, serv, ev):
        for language in self.joined:
            print "Voadaka. Mangataka tonga soa avy amin'i #" + language + ".wiktionary"
            serv.join("#" + language + ".wiktionary")

    def on_pubmsg(self, serv, ev):

        try:
            try:
                message = ev.arguments()[0].decode('utf8')
            except UnicodeDecodeError:
                message = ev.arguments()[0].decode('latin1')
            lang = 'fr'  # fiteny defaulta

            # Fitadiavana ny wiki niavian'ilay hafatra
            try:
                lang = re.search('//([a-z|\-]+).wiktionary', message).groups()[0]
            except AttributeError:
                pwbot.output(message)

            # Fijerena ny teny iditra & fanamboarana ny zavatra mamaritra azy.
            message = message[:message.find('http')]
            item = re.search("\[\[(.*)\]\]", message).groups()[0]
            item = unicode(item[3:-3])
            if len(item) > 70: return
            self.stats['edits'] += 1.
            if item.find(':') != -1:
                return
            page = pwbot.Page(pwbot.Site(lang, 'wiktionary'), item)

            # teny iditra vokatra
            #  mamerina ny isan'ny pejy voaforona
            self.stats['newentries'] += self.translations.process_wiktionary_page(lang, page)

            self.stats['rend'] = 100. * self.stats['errors'] / self.stats['edits']
            self.stats['rendpejy'] = 100. * float(self.stats['newentries']) / self.stats['edits']

            # interwiki vokatra
            self.translations.process_interwiki(lang, page)

            # Fanehoana ny statistika
            if not self.stats["edits"] % 5:
                cttime = time.gmtime()
                self.chronometer = time.time() - self.chronometer
                print "%d/%02d/%02d %02d:%02d:%02d > " % cttime[:6], \
                    "Fanovana: %(edits)d; pejy voaforona: %(newentries)d; hadisoana: %(errors)d" % self.stats \
                    + " taha: fanovana %.1f/min" % (
                        60. * (5 / self.chronometer))
                self.chronometer = time.time()

            # fanavaozana ny isan'ny dikanteny
            tran_hour = time.gmtime()[3]
            if self.tran_per_hour.translations_per_hour.has_key(tran_hour):
                self.tran_per_hour.translations_per_hour[tran_hour] += 1
            else:
                self.tran_per_hour.translations_per_hour[tran_hour] = 1
            self.tran_per_hour.update()

        except Exception as e:
            print traceback.format_exc()
            self.stats['errors'] += 1
            errstr = u"\n%s" % e.message
            self.errfile.write(errstr.encode('utf8'))


def striplinks(link):
    l = link
    for c in ['[', ']']:
        l = l.replace(c, '')
    return l


args = sys.argv
if __name__ == '__main__':
    Missing_translations = MissingTranslations(data_file)
    argsdict = {
        'irc': irc_retrieve,
        'debug': testTranslate,
        'analyse': analyse_translations,
        'edittimes': analyse_edit_hours,
        'addtranslations': add_translations
    }
    try:
        # verbose=True
        # print args[1] + " --- " + args[2]
        argsdict[args[1]](args[2])
    finally:
        pwbot.stopme()
