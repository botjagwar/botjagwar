import random
import re
import time
import os
import traceback
import requests
from modules import ircbot

userdata_file = os.getcwd() + '/user_data/dikantenyvaovao/'
nwikimax = 5


def irc_retrieve():
    wiktionary_bot = WiktionaryRecentChangesBot()
    while True:
        try:
            wiktionary_bot.start()
        except KeyboardInterrupt:
            wiktionary_bot.die()
            break


class IrcBotException(Exception):
    pass


class WiktionaryRecentChangesBot(ircbot.SingleServerIRCBot):
    """IRC client used to track edits on targetted wikis.
    @lang string containing languages of editions to track.
    For example : fr,en,de will track fr.wiktionary, en.wiktionary and de.wiktionary
    @user the username which will be use by the IRC client
    """

    def __init__(self, nick_prefix="botjagwar"):
        nick_suffix = '-%s' % base36encode(random.randint(36**3, 36**4 - 1))
        user = nick_prefix + nick_suffix
        self.channels_list = []
        self.chronometer = 0.0
        self.service_address = "http://localhost:8000"
        self.joined = []
        self.langs = []
        self.stats = {'edits': 0.0, 'newentries': 0.0, 'errors': 0.0}
        self.edits = 0
        self.username = user

        self.connect_in_languages()


    def connect_in_languages(self):
        """mametaka fitohizana amin'ny tsanely irc an'i Wikimedia"""
        print ("\n---------------------\nIRC BOT PAREMETERS : ")
        self.langs = ['en', 'fr']
        self.sitename = 'wiktionary'
        self.channels = ["#%s.%s" % (language.strip(), self.sitename) for language in self.langs]

        for channel in self.channels:
            ircbot.SingleServerIRCBot.__init__(
                self, [("irc.wikimedia.org", 6667)], self.username, "Bot-Jagwar [IRCbot v2].")
            self.joined.append(channel)
            print ("Channel:", channel, " Nickname:", self.username)

        print ("Connection complete")

    def do_join(self, serv, ev):
        for channel in self.joined:
            serv.join(channel)

    def on_welcome(self, serv, ev):
        self.do_join(serv, ev)

    def on_kick(self, serv, ev):
        self.do_join(serv, ev)

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
                print ("Edit #%d (%.2f edits/min)" % (self.edits, throughput))
        except requests.ConnectionError as e:
            print (traceback.format_exc())
            print 'NOTE: Launch dikantenyvaovao.py in a separate process to have the backend.'
        except Exception as e:
            print (traceback.format_exc())

            self.stats['errors'] += 1


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


def base36encode(number, alphabet='0123456789abcdefghjiklmnopqrstuvwxyz'):
    """Converts an integer to a base36 string."""
    if not isinstance(number, (int, long)):
        raise TypeError('number must be an integer')

    base36 = ''
    sign = ''

    if number < 0:
        sign = '-'
        number = -number

    if 0 <= number < len(alphabet):
        return sign + alphabet[number]

    while number != 0:
        number, i = divmod(number, len(alphabet))
        base36 = alphabet[i] + base36

    return sign + base36


if __name__ == '__main__':
    try:
        irc_retrieve()
    finally:
        print "bye"