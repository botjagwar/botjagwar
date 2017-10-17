from modules.entryprocessor.test import (
    TestFRWiktionary,
    TestDEWiktionary,
    TestENWiktionary)

from news_stats import get_milestones


class TestDikantenyVaovaoBot(object):
    def test_get_origin_wiki(self):
        pass

    def test_update_statistics(self):
        pass

    def test_process_wiktionary_page(self):
        # mock page.get
        # mock page.put
        pass


class TestDikantenyVaovaoProcessWiktionaryPage(object):
    def test_process_wiktionary_page_english(self):
        pass

    def test_process_wiktionary_page_french(self):
        pass


class TestTranslation(object):
    def test_code_to_name(self):
        pass

    def test_generate_redirections(self):
        pass

    def test_translation_from_bridge_language(self):
        pass


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
