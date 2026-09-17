"""Pytest configuration for deterministic offline test runs."""

import mwparserfromhell.parser

mwparserfromhell.parser.use_c = False
