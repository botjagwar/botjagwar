import random
import re
import time
import os
import traceback
import requests
from modules import ircbot

userdata_file = os.getcwd() + '/user_data/dikantenyvaovao/'
nwikimax = 5

def irc_retrieve(channel=''):
    bot = LiveRecentChangesBot(channel)
    while 1:
        try:
            bot.start()
        except KeyboardInterrupt:
            bot.die()
            return

class IrcBotException(Exception):
    pass

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
        self.service_address = "http://localhost:8000"
        try:
            self.errfile = open(userdata_file + 'dikantenyvaovao.exceptions', 'a')
        except IOError:
            self.errfile = open(userdata_file + 'dikantenyvaovao.exceptions', 'w')
        self.joined = []
        self.langs = []
        self.stats = {'edits': 0.0, 'newentries': 0.0, 'errors': 0.0}
        self.edits = 0
        self.username = user

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
            msg = _prepare_message(ev)
            wikilanguage = _get_origin_wiki(msg)
            pagename = _get_pagename(msg)
            url = self.service_address + "/wiktionary_page/%s" % (wikilanguage)
            data = {u'title': pagename}
            requests.post(url, json=data)
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

def _get_origin_wiki(message):
    try:
        lang = re.search('//([a-z|\-]+).wiktionary', message).groups()[0]
        return lang
    except AttributeError:
        lang = 'fr'  # fiteny defaulta
        return lang

def _get_pagename(message):
    message = message[:message.find('http')]
    item = re.search("\[\[(.*)\]\]", message).groups()[0]
    item = unicode(item[3:-3])
    if len(item) > 200:
        print (item)
        raise IrcBotException("Title is too long")
    return item


def _get_message_type(message):
    if "Log/delete" in message:
        return "delete"
    else:
        return "edit"


def _prepare_message(ev):
    try:
        message = ev.arguments()[0].decode('utf8')
    except UnicodeDecodeError:
        message = ev.arguments()[0].decode('latin1')
    return message

if __name__ == '__main__':
    try:
        irc_retrieve()
    finally:
        print "bye"