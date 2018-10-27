#!/bin/bash

set -e

cd /opt/botjagwar
INTERPRETER=python3.6

echo "spawning new process"
$INTERPRETER wiktionary_irc.py &