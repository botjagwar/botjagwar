#!/bin/bash

set -e

cd $HOME/botjagwar

if ! ps aux | grep python | grep fitenytsyfantatra
then
	python fitenytsyfantatra.py
fi
