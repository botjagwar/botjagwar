#!/bin/bash

set -e

cd $HOME/botjagwar

if ! ps aux | grep python | grep dikantenyvaovao
then
	python dikantenyvaovao.py &
fi

if ! ps aux | grep python | grep ircbot
then
	python ircbot.py & echo $! >>/tmp/ircbot.pid
fi