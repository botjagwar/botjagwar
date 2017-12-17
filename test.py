# coding: utf8

import json
import requests
from models import BaseEntry
from modules.translation.core import Translation
from news_stats import get_milestones
from test_utils.mocks import PageMock, SiteMock
from unittest.case import TestCase

LIST = [
    u"gaon", u"kid", u"精液", u"instar", u"bobos", u"大越",
]


class TestDikantenyVaovaoProcessWiktionaryPage(TestCase):

    def test_process_wiktionary_page_english(self):
        for pagename in LIST:
            translation = Translation()
            page = PageMock(SiteMock('en', 'wiktionary'), pagename)
            translation.process_wiktionary_page(u'en', page)

    def test_process_wiktionary_page_french(self):
        for pagename in LIST:
            translation = Translation()
            page = PageMock(SiteMock('fr', 'wiktionary'), pagename)
            translation.process_wiktionary_page(u'fr', page)


class _TestDikantenyVaovaoServices(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def check_response_status(self, url, data):
        resp = requests.put(url, json=data)
        print (resp.text)
        resp_data = json.loads(resp.text) if resp.text else {}
        self.assertEquals(resp.status_code, 200)
        for _, added_entries in resp_data.items():
            self.assertTrue(isinstance(added_entries , list))

    def test_translate_english_word(self):
        data = {
            u"dryrun": True,
            u"word": u"rice",
            u"translation": u"vary",
            u"POS": u"ana",
        }
        url = "http://localhost:8000/translate/en"
        self.check_response_status(url, data)

    def test_translate_french_word(self):
        data = {
            u"dryrun": True,
            u"word": u"riz",
            u"translation": u"vary",
            u"POS": u"ana",
        }
        url = "http://localhost:8000/translate/fr"
        self.check_response_status(url, data)


class TestModels(TestCase):

    def test_instantiate_base(self):
        test = BaseEntry(
            test1=10,
            test2=20,
            test3=300
        )
        self.assertEquals(test.test1, 10)
        self.assertEquals(test.test2, 20)
        self.assertEquals(test.test3, 300)

    def test_instantiate_child_class_additional_properties(self):
        class QingChuan(BaseEntry):
            _additional = True
            properties_types = {
                "test1": int,
                "test2": int
            }

        test = QingChuan(
            test1=1,
            test2=2,
            test3=u"klew"  # additional!
        )
        self.assertEquals(test.test1, 1)
        self.assertEquals(test.test2, 2)
        self.assertEquals(test.test3, u"klew")

    def test_instantiate_child_class_no_additional_properties(self):

        class GuoHang(BaseEntry):
            _additional = False
            properties_types = {
                "test1": int,
                "test2": int
            }

        def do_checks():
            test = GuoHang(
                test1=1,
                test2=2,
                test3=u"klew"  # additional!
            )
            self.assertEquals(test.test1, 1)
            self.assertEquals(test.test2, 2)
            self.assertEquals(test.test3, u"klew")

        self.assertRaises(AttributeError, do_checks)

class TestNewsStats(object):
    def test_milestone_detection(self):
        old = [
            ('mg', 'wiktionary',
             {u'articles': 100, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('az', 'wiktionary',
             {u'articles': 202, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('dv', 'wiktionary',
             {u'articles': 100, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('kz', 'wiktionary',
             {u'articles': 212, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('dj', 'wiktionary',
             {u'articles': 122, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('pa', 'wiktionary',
             {u'articles': 202, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('de', 'wiktionary',
             {u'articles': 100, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('ke', 'wiktionary',
             {u'articles': 202, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('es', 'wiktionary',
             {u'articles': 1, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0, u'images': 0,
              u'queued-massmessages': 0, u'pages': 67}),
            ('ml', 'wiktionary',
             {u'articles': 100, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('kn', 'wiktionary',
             {u'articles': 202, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('dk', 'wiktionary',
             {u'articles': 100, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('kl', 'wiktionary',
             {u'articles': 202, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('se', 'wiktionary',
             {u'articles': 1, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0, u'images': 0,
              u'queued-massmessages': 0, u'pages': 67}),
            ('sv', 'wiktionary',
             {u'articles': 202, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('fi', 'wiktionary',
             {u'articles': 100, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('uz', 'wiktionary',
             {u'articles': 202, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('uk', 'wiktionary',
             {u'articles': 1, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0, u'images': 0,
              u'queued-massmessages': 0, u'pages': 67})
        ]

        new = [
            ('mg', 'wiktionary',
             {u'articles': 100, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('az', 'wiktionary',
             {u'articles': 202, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 30486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('dv', 'wiktionary',
             {u'articles': 300, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('kz', 'wiktionary',
             {u'articles': 412, u'jobs': 0, u'users': 10400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('dj', 'wiktionary',
             {u'articles': 522, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 30486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('pa', 'wiktionary',
             {u'articles': 602, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('de', 'wiktionary',
             {u'articles': 10, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0, u'images': 0,
              u'queued-massmessages': 0, u'pages': 67}),
            ('ke', 'wiktionary',
             {u'articles': 702, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('es', 'wiktionary',
             {u'articles': 820, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 30486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('ml', 'wiktionary',
             {u'articles': 900, u'jobs': 0, u'users': 1431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('kn', 'wiktionary',
             {u'articles': 1202, u'jobs': 0, u'users': 400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('dk', 'wiktionary',
             {u'articles': 1200, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('kl', 'wiktionary',
             {u'articles': 1502, u'jobs': 0, u'users': 2400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('se', 'wiktionary',
             {u'articles': 2000, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('sv', 'wiktionary',
             {u'articles': 3002, u'jobs': 0, u'users': 4400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('fi', 'wiktionary',
             {u'articles': 4000, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('uz', 'wiktionary',
             {u'articles': 5002, u'jobs': 0, u'users': 5400, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67}),
            ('uk', 'wiktionary',
             {u'articles': 6000, u'jobs': 0, u'users': 431, u'admins': 0, u'edits': 3486, u'activeusers': 0,
              u'images': 0, u'queued-massmessages': 0, u'pages': 67})
        ]

        expected = [
            ('az', 'wiktionary', 'over', 30000, u'edits'),
            ('kz', 'wiktionary', 'over', 10000, u'users'),
            ('dj', 'wiktionary', 'over', 30000, u'edits'),
            ('de', 'wiktionary', 'below', 10, u'articles'),
            ('es', 'wiktionary', 'over', 800, u'articles'),
            ('es', 'wiktionary', 'over', 30000, u'edits'),
            ('ml', 'wiktionary', 'over', 1000, u'users'),
            ('kn', 'wiktionary', 'over', 1000, u'articles'),
            ('dk', 'wiktionary', 'over', 1000, u'articles'),
            ('kl', 'wiktionary', 'over', 1000, u'articles'),
            ('kl', 'wiktionary', 'over', 2000, u'users'),
            ('se', 'wiktionary', 'over', 2000, u'articles'),
            ('sv', 'wiktionary', 'over', 3000, u'articles'),
            ('sv', 'wiktionary', 'over', 4000, u'users'),
            ('fi', 'wiktionary', 'over', 4000, u'articles'),
            ('uz', 'wiktionary', 'over', 5000, u'articles'),
            ('uz', 'wiktionary', 'over', 5000, u'users'),
            ('uk', 'wiktionary', 'over', 6000, u'articles')]

        got = [i for i in get_milestones(old, new)]
        got.sort()
        expected.sort()
        assert got == expected
