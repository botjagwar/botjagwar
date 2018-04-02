#!/bin/bash

set -e

cd /opt/botjagwar
INTERPRETER=python3.6

if ps aux | grep python | grep wiktionary_irc
then
	echo "killing old process"
	if [ -e /tmp/ircbot.pid ]
	then
		kill -9 `cat /tmp/ircbot.pid`
	fi

	echo "deleting PID file"
	rm /tmp/ircbot.pid
fi

echo "spawning new process"
$INTERPRETER wiktionary_irc.py & echo $! > /tmp/ircbot.pid