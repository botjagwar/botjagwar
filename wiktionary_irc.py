#!/usr/bin/python3
import logging as log
import os
import random
import re
import time
from signal import SIGTERM

import irc.bot
import requests

from api.decorator import retry_on_fail
from api.servicemanager import EntryTranslatorServiceManager

log.basicConfig(filename="/opt/botjagwar/user_data/wiktionary_irc.log", level=log.DEBUG)
userdata_file = "/opt/botjagwar/user_data/entry_translator/"
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

    recent_change_server = ("irc.wikimedia.org", 6667)

    def __init__(self, nick_prefix="botjagwar"):
        nick_suffix = f"-{base36encode(random.randint(36**3, 36**4 - 1))}"
        user = nick_prefix + nick_suffix
        self.channels_list = []
        super(WiktionaryRecentChangesBot, self).__init__(
            self.channels_list, user, user, 5
        )

        self.chronometer = 0.0
        self.joined = []
        self.langs = []
        self.stats = {"edits": 0.0, "newentries": 0.0, "errors": 0.0}
        self.edits = 0
        self.username = user
        self.entry_translator_manager = EntryTranslatorServiceManager()
        self.connect_in_languages()

    def connect_in_languages(self):
        """mametaka fitohizana amin'ny tsanely irc an'i Wikimedia"""
        print("\n---------------------\nIRC BOT PAREMETERS : ")
        self.langs = ["en", "fr"]
        self.sitename = "wiktionary"
        self.channels = [
            f"#{language.strip()}.{self.sitename}" for language in self.langs
        ]
        for channel in self.channels:
            irc.bot.SingleServerIRCBot.__init__(
                self,
                [self.recent_change_server],
                self.username,
                "Bot-Jagwar [IRCbot v2].",
            )
            self.joined.append(channel)
            print(("Channel:", channel, " Nickname:", self.username))

        print("Connection complete")

    def do_join(self, server, events):
        for channel in self.joined:
            server.join(channel)

    def on_welcome(self, server, events):
        self.do_join(server, events)

    def on_kick(self, server, events):
        self.do_join(server, events)

    def on_pubmsg(self, server, events):
        @retry_on_fail([requests.ConnectionError], 10, 0.3)
        def _process():
            try:
                ct_time = time.time()
                msg = _prepare_message(events)
                self.entry_translator_manager.post(
                    f"wiktionary_page/{_get_origin_wiki(msg)}",
                    json={"title": _get_pagename(msg)},
                )
                self.edits += 1
                if not self.edits % 5:
                    throughput = 60.0 * 5.0 / (float(ct_time) - self.chronometer)
                    self.chronometer = ct_time
                    print(("Edit #%d (%.2f edits/min)" % (self.edits, throughput)))
            except requests.ConnectionError as e:
                print('NOTE: Spawning "entry_processor.py" backend process.')
            except Exception as e:
                log.exception(e)
                self.stats["errors"] += 1

        _process()


def _get_origin_wiki(message):
    try:
        return re.search(r"//([a-z|\-]+).wiktionary", message).groups()[0]
    except AttributeError:
        return "fr"


def _get_pagename(message):
    message = message[: message.find("http")]
    item = re.search(r"\[\[(.*)\]\]", message).groups()[0]
    item = str(item[3:-3])
    if len(item) > 200:
        print(item)
        raise IrcBotException("Title is too long")
    return item


def _get_message_type(message):
    return "delete" if "Log/delete" in message else "edit"


def _prepare_message(events):
    return events.arguments[0]


def base36encode(number, alphabet="0123456789abcdefghjiklmnopqrstuvwxyz"):
    """Converts an integer to a base36 string."""
    if not isinstance(number, int):
        raise TypeError("number must be an integer")

    base36 = ""
    sign = ""

    if number < 0:
        sign = "-"
        number = -number

    if 0 <= number < len(alphabet):
        return sign + alphabet[number]

    while number != 0:
        number, i = divmod(number, len(alphabet))
        base36 = alphabet[i] + base36

    return sign + base36


def kill_other_instance():
    log.info("Killing old wiktionary_irc process")
    pid = None
    path = "/tmp/ircbot.pid"
    try:
        with open(path, "r") as f:
            pid = int(f.read())
    except FileNotFoundError:
        print("File /tmp/ircbot.pid not found")

    if pid is not None:
        try:
            print("Checking the existence of the process %d" % pid)
            os.kill(pid, 0)
        except OSError:
            print("Process no longer exists... removing the pid file")
        else:
            print("A process exists...")
            os.kill(pid, SIGTERM)


if __name__ == "__main__":
    try:
        kill_other_instance()
        with open("/tmp/ircbot.pid", "w") as f:
            f.write("%d" % os.getpid())
        irc_retrieve()
    finally:
        print("bye")
