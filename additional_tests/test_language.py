import json
import os
from subprocess import PIPE
from subprocess import Popen
from time import sleep
from unittest import TestCase

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.decorator import threaded, retry_on_fail
from database.dictionary import Base
from database.exceptions.http import InvalidJsonReceived

URL_HEAD = 'http://0.0.0.0:8003'
DB_PATH = '/tmp/test_language.db'


class TestLanguageRestService(TestCase):
    def setUp(self):
        self.ENGINE = create_engine('sqlite:///%s' % DB_PATH)
        Base.metadata.create_all(self.ENGINE)
        SessionClass = sessionmaker(bind=self.ENGINE)
        session = SessionClass()

        self.launch_service()
        self.wait_until_ready()

        self.create_language('chq', 'zhenquang', 'tsanitsioangy')

        session.commit()
        session.flush()

    def tearDown(self):
        self.kill_service()
        sleep(.4)

    @staticmethod
    @threaded
    def launch_service():
        global DICTIONARY_SERVICE
        DICTIONARY_SERVICE = Popen(["python3",
                                    "language_service.py",
                                    '--db-file',
                                    DB_PATH],
                                   stdin=PIPE,
                                   stdout=PIPE,
                                   stderr=PIPE)
        DICTIONARY_SERVICE.communicate()

    @retry_on_fail([Exception], retries=10, time_between_retries=.4)
    def wait_until_ready(self):
        resp = requests.get(URL_HEAD + '/ping')
        assert resp.status_code == 200

    @staticmethod
    def kill_service():
        DICTIONARY_SERVICE.kill()
        os.system('rm %s' % DB_PATH)

    @retry_on_fail([Exception], 10, .3)
    def create_language(self, code, english_name, malagasy_name):
        resp = requests.post(
            URL_HEAD + '/language/%s' % code,
            json=json.dumps({
                'english_name': english_name,
                'malagasy_name': malagasy_name,
                'iso_code': code
            })
        )
        self.assertEquals(resp.status_code, 200)

    def test_disable_autocommit(self):
        requests.put(
            URL_HEAD + '/configure',
            json=json.dumps({
                'autocommit': False
            })
        )
        for i in range(20):
            self.create_language(
                'zh%d' %
                i,
                'zhenquang%d' %
                i,
                'tsanitsioangy%d' %
                i)

        requests.post(URL_HEAD + '/rollback')

        for i in range(20):
            resp = requests.get(URL_HEAD + '/language/zh%d' % i)
            self.assertEquals(resp.status_code, 404)

    def test_enable_autocommit(self):
        requests.put(
            URL_HEAD + '/configure',
            json=json.dumps({
                'autocommit': False
            })
        )
        for i in range(20):
            self.create_language(
                'zh%d' %
                i,
                'zhenquang%d' %
                i,
                'tsanitsioangy%d' %
                i)

        for i in range(20):
            resp = requests.get(URL_HEAD + '/language/zh%d' % i)
            self.assertEquals(resp.status_code, 200)

    def test_get_language(self):
        self.create_language('ch0', 'zhenquang', 'tsanitsioangy')
        resp = requests.get(URL_HEAD + '/language/ch0')
        data = resp.json()
        self.assertEquals(resp.status_code, 200)
        self.assertEquals(data['iso_code'], 'ch0')
        self.assertEquals(data['malagasy_name'], 'tsanitsioangy')
        self.assertEquals(data['english_name'], 'zhenquang')

    def test_get_language_404(self):
        resp = requests.get(URL_HEAD + '/language/c9')
        self.assertEquals(resp.status_code, 404)

    def test_create_language(self):
        self.create_language('ch10', 'zhenquang', 'tsanitsioangy')

    def test_create_existing_entry(self):
        resp = requests.post(
            URL_HEAD + '/language/ali',
            json=json.dumps({
                'english_name': 'asdlksd',
                'malagasy_name': 'asdlksd',
                'iso_code': 'as'
            })
        )
        self.assertEquals(resp.status_code, 200)
        resp = requests.post(
            URL_HEAD + '/language/ali',
            json=json.dumps({
                'english_name': 'asdasdasdlksd',
                'malagasy_name': 'asdlkasdsadsd',
                'iso_code': 'as'
            })
        )
        self.assertEquals(resp.status_code, 460)

    def test_create_entry_invalid_json(self):
        resp = requests.post(
            URL_HEAD + '/language/sdl',
            json=json.dumps({
                'iso_coed': 'sdl',
                'langauge': 'aslks',
                'engilsh_naem': 'alskasd',
            })
        )
        self.assertEquals(
            resp.status_code,
            InvalidJsonReceived.status_code)

    def test_edit_entry(self):
        resp = requests.get(URL_HEAD + '/language/chq')
        data = resp.json()
        resp = requests.put(
            URL_HEAD + '/language/ch0/edit',
            json=json.dumps({
                'malagasy_name': 'alkqwj',
                'english_name': 'asldk',
                'iso_code': 'chq'
            })
        )
        self.assertEquals(resp.status_code, 200)

    def test_read_after_write_get_after_delete(self):
        self.test_delete_language()
        resp = requests.get(URL_HEAD + '/language/chq')
        self.assertEquals(resp.status_code, 404)

    def test_delete_language(self):
        resp = requests.get(URL_HEAD + '/language/chq')
        self.assertEquals(resp.status_code, 200)

        del_url = URL_HEAD + '/language/chq'
        resp = requests.delete(del_url)
        self.assertEquals(resp.status_code, 204)
