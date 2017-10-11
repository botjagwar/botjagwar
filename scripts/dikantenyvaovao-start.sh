#!/bin/bash

set -e

cd $(HOME)/botjagwar

if ! ps aux | grep python | grep dikantenyvaovao
then
	python dikantenyvaovao.py irc 0
fi
