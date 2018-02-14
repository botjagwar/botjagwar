import random
import re
import time
import os

import irc.bot
import requests
from subprocess import Popen
import traceback

from modules.decorator import threaded

userdata_file = os.getcwd() + '/user_data/entry_translator/'
nwikimax = 5
spawned_backend_process = None
dictionary_service = None


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


class WiktionaryRecentChangesBot(irc.bot.SingleServerIRCBot):
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
            irc.bot.SingleServerIRCBot.__init__(
                self, [("irc.wikimedia.org", 6667)], self.username, "Bot-Jagwar [IRCbot v2].")
            self.joined.append(channel)
            print(("Channel:", channel, " Nickname:", self.username))

        try:
            requests.put(self.service_address + '/configure', json={'autocommit': True})
        except requests.exceptions.ConnectionError:
            spawn_backend()
            time.sleep(2)
            requests.put(self.service_address + '/configure', json={'autocommit': True})

        print ("Connection complete")

    def do_join(self, server, events):
        for channel in self.joined:
            server.join(channel)

    def on_welcome(self, server, events):
        self.do_join(server, events)

    def on_kick(self, server, events):
        self.do_join(server, events)

    def on_pubmsg(self, server, events):
        try:
            ct_time = time.time()
            msg = _prepare_message(events)
            wikilanguage = _get_origin_wiki(msg)
            pagename = _get_pagename(msg)
            url = self.service_address + "/wiktionary_page/%s" % (wikilanguage)
            data = {'title': pagename}
            requests.post(url, json=data)
            self.edits += 1
            if not self.edits % 5:
                throughput = 60. * 5. / (float(ct_time) - self.chronometer)
                self.chronometer = ct_time
                print(("Edit #%d (%.2f edits/min)" % (self.edits, throughput)))
        except requests.ConnectionError as e:
            print((traceback.format_exc()))
            print('NOTE: Spawning "entry_processor.py" backend process.')
        except Exception as e:
            print((traceback.format_exc()))

            self.stats['errors'] += 1


def _get_origin_wiki(message):
    try:
        lang = re.search(r'//([a-z|\-]+).wiktionary', message).groups()[0]
        return lang
    except AttributeError:
        lang = 'fr'  # fiteny defaulta
        return lang


def _get_pagename(message):
    message = message[:message.find('http')]
    item = re.search(r"\[\[(.*)\]\]", message).groups()[0]
    item = str(item[3:-3])
    if len(item) > 200:
        print (item)
        raise IrcBotException("Title is too long")
    return item


def _get_message_type(message):
    if "Log/delete" in message:
        return "delete"
    else:
        return "edit"


def _prepare_message(events):
    return events.arguments()[0]


def base36encode(number, alphabet='0123456789abcdefghjiklmnopqrstuvwxyz'):
    """Converts an integer to a base36 string."""
    if not isinstance(number, int):
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


@threaded
def spawn_backend():
    spawned_backend_process = Popen(['python3.6', 'entry_translator.py'])
    dictionary_service = Popen(['python3.6', 'dictionary_service.py'])
    spawned_backend_process.communicate()
    dictionary_service.communicate()


if __name__ == '__main__':
    try:
        irc_retrieve()
    finally:
        if spawned_backend_process is not None:
            spawned_backend_process.terminate()
        if dictionary_service is not None:
            dictionary_service.terminate()
        print("bye")