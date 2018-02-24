#!/bin/bash

set -e

cd $HOME/botjagwar
INTERPRETER=python3.6

if ! ps aux | grep python | grep wiktionary_irc
then
	$INTERPRETER wiktionary_irc.py & echo $! > /tmp/ircbot.pid
fi