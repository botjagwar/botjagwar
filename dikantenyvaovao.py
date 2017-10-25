# -*- coding: utf8 -*-
import time
import re
import sys
import os
import random
import traceback
import pywikibot as pwbot
from modules import ircbot
from modules.decorator import threaded
from modules.translation.core import Translation

# GLOBAL VARS
verbose = False
nwikimax = 5
databases = []
data_file = os.getcwd() + '/conf/dikantenyvaovao/'
userdata_file = os.getcwd() + '/user_data/dikantenyvaovao/'


def irc_retrieve(channel=''):
    set_throttle(1)
    bot = LiveRecentChangesBot(channel)
    while 1:
        try:
            bot.start()
        except KeyboardInterrupt:
            bot.die()
            return


# Throttle Config
def set_throttle(i):
    from pywikibot import throttle
    t = throttle.Throttle(pwbot.Site('mg', 'wiktionary'), mindelay=0, maxdelay=1)
    pwbot.config.put_throttle = 1
    t.setDelays(i)


class LiveRecentChangesBot(ircbot.SingleServerIRCBot):
    """IRC client used to track edits on targetted wikis.
    @lang string containing languages of editions to track.
    For example : fr,en,de will track fr.wiktionary, en.wiktionary and de.wiktionary
    @user the username which will be use by the IRC client
    """

    def __init__(self, lang, user="botjagwar-w%x" % random.randint(1, 0xffff)):
        self.channels_list = []
        self.chronometer = 0.0
        self.change_langs(lang)
        try:
            self.errfile = open(userdata_file + 'dikantenyvaovao.exceptions', 'a')
        except IOError:
            self.errfile = open(userdata_file + 'dikantenyvaovao.exceptions', 'w')
        self.iso2languagename = {}
        self.joined = []
        self.langs = []
        self.stats = {'edits': 0.0, 'newentries': 0.0, 'errors': 0.0}
        self.edits = 0
        self.username = user
        self.bot_instance = Bot()

        self.connect_in_languages()

    def change_langs(self, langstring):
        self.langs = re.split("\,[ ]?", langstring)

    def connect_in_languages(self):
        """mametaka fitohizana amin'ny tsanely irc an'i Wikimedia"""
        print ("\n---------------------\n       PARAMETATRA : ")
        self.langs = ['en', 'fr']
        i = 0
        for language in self.langs:
            if i > nwikimax:
                break
            i += 1
            if language == 'mg':
                continue
            language = language.strip()
            channel = "#%s.wiktionary" % language
            print ("kaodim-piteny:", language, ", tsanely:", channel, " anarana:", self.username)

            irc_bot = ircbot.SingleServerIRCBot.__init__(
                self, [("irc.wikimedia.org", 6667)], self.username, "Bot-Jagwar [IRCbot v2].")
            self.joined.append(language)
            self.channels_list.append(irc_bot)
        print ("Vita ny fampitohizana")

    def on_welcome(self, serv, ev):
        for language in self.joined:
            # print ("Mangataka tonga soa avy amin'i #"+language+".wiktionary")
            serv.join("#" + language + ".wiktionary")

    def on_kick(self, serv, ev):
        for language in self.joined:
            print ("Voadaka. Mangataka tonga soa avy amin'i #" + language + ".wiktionary")
            serv.join("#" + language + ".wiktionary")

    def on_pubmsg(self, serv, ev):
        try:
            ct_time = time.time()
            self.bot_instance.handle(ev)
            self.edits += 1
            if not self.edits % 5:
                throughput = 60. * 5. / (float(ct_time) - self.chronometer)
                self.chronometer = ct_time
                print ("Fiovana faha-%d (fiovana %.2f / min)" % (self.edits, throughput))

        except Exception as e:
            print (traceback.format_exc())
            self.stats['errors'] += 1
            errstr = u"\n%s" % e.message
            self.errfile.write(errstr.encode('utf8'))


class Bot(object):
    def __init__(self):
        self.translations = Translation(data_file)

    @staticmethod
    def _prepare_message(ev):
        try:
            message = ev.arguments()[0].decode('utf8')
        except UnicodeDecodeError:
            message = ev.arguments()[0].decode('latin1')
        return message

    @staticmethod
    def _update_unknowns(unknowns):
        f = open(userdata_file + "word_hits", 'a')
        for word, lang in unknowns:
            word += ' [%s]\n' % lang
            print (type(word))
            f.write(word.encode('utf8'))
        f.close()

    @staticmethod
    def _get_message_type(message):
        if "Log/delete" in message:
            return "delete"
        else:
            return "edit"

    @staticmethod
    def _get_page(message, lang):
        message = message[:message.find('http')]
        item = re.search("\[\[(.*)\]\]", message).groups()[0]
        item = unicode(item[3:-3])
        if len(item) > 70: return
        if item.find(':') != -1:
            return
        page = pwbot.Page(pwbot.Site(lang, 'wiktionary'), item)
        return page

    @staticmethod
    def _get_origin_wiki(message):
        try:
            lang = re.search('//([a-z|\-]+).wiktionary', message).groups()[0]
            return lang
        except AttributeError:
            lang = 'fr'  # fiteny defaulta
            pwbot.output(message)
            return lang

    @staticmethod
    def _update_statistics(rc_bot):
        if not rc_bot.stats["edits"] % 5:
            cttime = time.gmtime()
            rc_bot.chronometer = time.time() - rc_bot.chronometer
            print ("%d/%02d/%02d %02d:%02d:%02d > " % cttime[:6], \
                   "Fanovana: %(edits)d; pejy voaforona: %(newentries)d; hadisoana: %(errors)d" % rc_bot.stats \
                   + " taha: fanovana %.1f/min" % (60. * (5 / rc_bot.chronometer)))
            rc_bot.chronometer = time.time()

    @staticmethod
    @threaded
    def put_deletion_notice(page):
        if not page.exists() or page.isRedirectPage():
            return
        if page.namespace() == 0:
            page_c = page.get()
            page_c += u"\n[[sokajy:Pejy voafafa tany an-kafa]]"
            page.put(page_c, "+filazana")

    def handle(self, ev):
        message = self._prepare_message(ev)
        lang = self._get_origin_wiki(message)
        message_type = self._get_message_type(message)

        if message_type == 'edit':
            page = self._get_page(message, lang)
            if page is None:
                return
            unknowns, newentries = self.translations.process_wiktionary_page(lang, page)
            self._update_unknowns(unknowns)

        elif message_type == 'delete':
            page = self._get_page(message, 'mg')
            if page is None:
                return
            self.put_deletion_notice(page)


def striplinks(link):
    l = link
    for c in ['[', ']']:
        l = l.replace(c, '')
    return l


args = sys.argv
if __name__ == '__main__':
    try:
        irc_retrieve()
    finally:
        pwbot.stopme()
