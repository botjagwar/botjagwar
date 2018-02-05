import os
from time import sleep
from subprocess import Popen
from unittest import TestCase
import json
import requests

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from modules.decorator import threaded
from database import Base, Definition, Word

import database.http as db_http

URL_HEAD = 'http://localhost:8001'
DB_PATH = '/tmp/test.db'


class TestDictionaryRestService(TestCase):
    def setUp(self):
        self.ENGINE = create_engine('sqlite:///%s' % DB_PATH)
        Base.metadata.create_all(self.ENGINE)
        SessionClass = sessionmaker(bind=self.ENGINE)
        session = SessionClass()
        definition = Definition(definition='rikizimai',
                                definition_language='de')
        word = Word(word='tehanu',
                    language='jm',
                    part_of_speech='ana',
                    definitions=[definition])
        session.add(definition)
        session.add(word)

        session.commit()
        session.flush()

        self.launch_service()
        sleep(2.5)

    @threaded
    def launch_service(self):
        self.p2 = Popen(["python3.6", "dictionary.py",
                         '--db-file', '/tmp/test.db',
                         ])

    def tearDown(self):
        self.p2.kill()
        os.system('rm %s' % DB_PATH)

    def create_entry(self):
        resp = requests.post(
            URL_HEAD + '/entry/ka/create',
            json=json.dumps({
                'definitions': [{
                    'definition': 'tarameguni',
                    'definition_language': 'mg'
                }],
                'word': 'tejaos',
                'part_of_speech': 'ana',
            })
        )
        self.assertEquals(resp.status_code, 200)
        # check in database if definition has been added

    def test_get_entry(self):
        resp = requests.get(URL_HEAD + '/entry/jm/tehanu')
        data = resp.json()
        self.assertEquals(resp.status_code, 200)
        for datum in data:
            self.assertEquals(datum['word'], 'tehanu')
            self.assertEquals(datum['language'], 'jm')
            self.assertEquals(datum['part_of_speech'], 'ana')
            self.assertEquals(len(datum['definitions']), 1)

    def test_get_entry_404(self):
        resp = requests.get(URL_HEAD + '/entry/jm/teklkhanu')
        self.assertEquals(resp.status_code, 404)

    def test_create_entry(self):
        self.create_entry()

    def test_create_existing_entry(self):
        resp = requests.post(
            URL_HEAD + '/entry/jm/create',
            json=json.dumps({
                'definitions': [{
                    'definition': 'nanganasla',
                    'definition_language': 'mg'
                }],
                'word': 'tehanu',
                'part_of_speech': 'ana',
            })
        )
        self.assertEquals(
            resp.status_code,
            db_http.WordAlreadyExistsException.status_code)

    def test_create_entry_invalid_json(self):
        resp = requests.post(
            URL_HEAD + '/entry/jm/create',
            json=json.dumps({
                'word': 'tehanu',
                'part_of_speech': 'ana',
            })
        )
        self.assertEquals(
            resp.status_code,
            db_http.InvalidJsonReceivedException.status_code)

    def test_edit_entry(self):
        resp = requests.get(URL_HEAD + '/entry/jm/tehanu')
        data = resp.json()
        word_id = data[0]['id']
        resp = requests.put(
            URL_HEAD + '/entry/%d/edit' % word_id,
            json=json.dumps({
                'definitions': [{
                    'definition': 'tarameguni',
                    'definition_language': 'mg'
                }],
                'part_of_speech': 'aojs',
            })
        )
        self.assertEquals(resp.status_code, 200)

    def test_read_after_write_get_after_post(self):
        self.create_entry()

        resp = requests.get(URL_HEAD + '/entry/ka/tejaos')
        data = resp.json()
        self.assertEquals(resp.status_code, 200)
        for datum in data:
            self.assertEquals(datum['word'], 'tejaos')
            self.assertEquals(datum['language'], 'ka')
            self.assertEquals(datum['part_of_speech'], 'ana')
            self.assertEquals(len(datum['definitions']), 1)

    def test_read_after_write_get_after_put(self):
        self.test_edit_entry()

        resp = requests.get(URL_HEAD + '/entry/jm/tehanu')
        data = resp.json()
        self.assertEquals(resp.status_code, 200)
        for datum in data:
            self.assertEquals(datum['word'], 'tehanu')
            self.assertEquals(datum['language'], 'jm')
            self.assertEquals(datum['part_of_speech'], 'aojs')
            self.assertEquals(len(datum['definitions']), 1)

    def test_delete_entry(self):
        resp = requests.get(URL_HEAD + '/entry/jm/tehanu')
        self.assertEquals(resp.status_code, 200)

        data = resp.json()[0]
        del_url = URL_HEAD + '/entry/%d/delete' % data['id']
        resp = requests.delete(del_url)
        self.assertEquals(resp.status_code, 204)

    def test_read_after_write_get_after_delete(self):
        self.test_delete_entry()
        resp = requests.get(URL_HEAD + '/entry/jm/tehanu')
        self.assertEquals(resp.status_code, 404)

    def test_get_definition(self):
        resp = requests.get(URL_HEAD + '/definition/1')
        self.assertEquals(resp.status_code, 200)

    def test_search_definition(self):
        search_params = {
            'definition': 'rikizimai'
        }
        resp = requests.post(
            URL_HEAD + '/definition/search',
            json=json.dumps(search_params)
        )
        j = resp.json()
        self.assertEquals(len(j), 1)
        self.assertEquals(resp.status_code, 200)

    def test_search_definition_wildcard(self):
        search_params = {
            'definition': 'rik%'
        }
        resp = requests.post(
            URL_HEAD + '/definition/search',
            json=json.dumps(search_params)
        )
        j = resp.json()
        print(j)
        self.assertEquals(len(j), 1)
        self.assertEquals(resp.status_code, 200)

    def test_delete_definition(self):
        resp = requests.get(URL_HEAD + '/entry/jm/tehanu')
        self.assertEquals(resp.status_code, 200)

        data = resp.json()[0]
        del_url = URL_HEAD + '/entry/%d/delete' % data['id']
        resp = requests.delete(del_url)
        self.assertEquals(resp.status_code, 204)
