#!/bin/bash

set -e

cd $HOME/botjagwar

if ! ps aux | grep python | grep unknown_language_manager
then
	python unknown_language_manager.py
fi
