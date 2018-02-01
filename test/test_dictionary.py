import os
from time import sleep
from subprocess import Popen
from unittest import TestCase
import json
import requests

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from modules.decorator import threaded, retry_on_fail
from database import Base, Definition, Word

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
        data = resp.json()
        print (data)
        self.assertEquals(resp.status_code, 404)

    def add_entry(self):
        resp = requests.post(
            URL_HEAD + '/entry/en/totoro/add',
            json=json.dumps({
                'definitions': [{
                        'definition': 'tarameguni',
                        'definition_language': 'mg'
                }],
                'word': 'totoro',
                'language': 'en',
                'part_of_speech': 'ana',
            })
        )
        self.assertEquals(resp.status_code, 200)
        # check in database if definition has been added

    def test_edit_entry(self):
        resp = requests.put(
            URL_HEAD + '/entry/en/totoro/edit',
            json=json.dumps({
                'definitions': [{
                    'definition': 'tarameguni',
                    'definition_language': 'mg'
                }],
                'word': 'totoro',
                'language': 'en',
                'part_of_speech': 'ana',
            })
        )
        self.assertEquals(resp.status_code, 200)

        # check in database if entry has been changed

    def _test_append_definition(self):
        # TODO
        resp = requests.put(URL_HEAD + '/entry/jm/tehanu/append' % ())

    def _test_delete_definition(self):
        # TODO
        resp = requests.delete(URL_HEAD + '/entry/jm/tehanu' % ())

