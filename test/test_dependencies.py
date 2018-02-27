from unittest import TestCase


class TestDependencies(TestCase):
    def test_external_deps(self):
        import asyncio
        import aiohttp
        import flask
        import irc
        import json
        import lxml
        import oauthlib
        import pywikibot
        import requests
        import sqlalchemy