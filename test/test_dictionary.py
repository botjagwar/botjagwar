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
from database.dictionary import Base, Definition, Word
from database.exceptions.http import InvalidJsonReceivedException
from database.exceptions.http import WordAlreadyExistsException

URL_HEAD = 'http://0.0.0.0:8001'
DB_PATH = '/tmp/test.db'

# Temporarily patch requests API in case of refused connections (connecting while service is not ready)
possible_errors = [requests.exceptions.ConnectionError]
requests.post = retry_on_fail(possible_errors, retries=5, time_between_retries=.4)(requests.post)
requests.get = retry_on_fail(possible_errors, retries=5, time_between_retries=.4)(requests.get)
requests.put = retry_on_fail(possible_errors, retries=5, time_between_retries=.4)(requests.put)
requests.delete = retry_on_fail(possible_errors, retries=5, time_between_retries=.4)(requests.delete)


class TestDictionaryRestService(TestCase):
    def setUp(self):
        self.ENGINE = create_engine('sqlite:///%s' % DB_PATH)
        Base.metadata.create_all(self.ENGINE)
        SessionClass = sessionmaker(bind=self.ENGINE)
        session = SessionClass()
        definition = Definition('rikizimai', 'de')
        word = Word(word='tehanu',
                    language='jm',
                    part_of_speech='ana',
                    definitions=[definition])
        session.add(definition)
        session.add(word)

        self.launch_service()
        self.wait_until_ready()

        session.commit()
        session.flush()

    def tearDown(self):
        self.kill_service()
        sleep(.4)

    @staticmethod
    @threaded
    def launch_service():
        global DICTIONARY_SERVICE
        DICTIONARY_SERVICE = Popen(["python3.6", "dictionary_service.py", '--db-file', DB_PATH],
                                   stdin=PIPE, stdout=PIPE, stderr=PIPE)
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
    def create_entry(self, word, language, pos, definition, def_language):
        resp = requests.post(
            URL_HEAD + '/entry/%s/create' % language,
            json=json.dumps({
                'definitions': [{
                    'definition': definition,
                    'definition_language': def_language
                }],
                'word': word,
                'part_of_speech': pos,
            })
        )
        self.assertEquals(resp.status_code, 200)
        j = resp.json()
        # check in database if definition has been added

    def test_disable_autocommit(self):
        requests.put(
            URL_HEAD + '/configure',
            json=json.dumps({
                'autocommit': False
            })
        )
        for i in range(20):
            self.create_entry('nanaika%d' % i, 'ka', 'ana', 'tarameguni%d' % i, 'de')

        requests.post(URL_HEAD + '/rollback')

        for i in range(20):
            resp = requests.get(URL_HEAD + '/entry/ka/nanaika%d' % i)
            self.assertEquals(resp.status_code, 404)

    def test_enable_autocommit(self):
        requests.put(
            URL_HEAD + '/configure',
            json=json.dumps({
                'autocommit': True
            })
        )
        for i in range(20):
            self.create_entry('nanaika%d' % i, 'ka', 'ana', 'tarameguni%d' % i, 'de')

        for i in range(20):
            resp = requests.get(URL_HEAD + '/entry/ka/nanaika%d' % i)
            self.assertEquals(resp.status_code, 200)

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
        self.create_entry('nakaina', 'jm', 'ana', 'tarameguni', 'de')

    def test_create_existing_entry(self):
        sleep(1)
        resp = requests.post(
            URL_HEAD + '/entry/jm/create',
            json=json.dumps({
                'definitions': [{
                    'definition': 'rikizimai',
                    'definition_language': 'de'
                }],
                'word': 'tehanu',
                'part_of_speech': 'ana',
            })
        )
        self.assertEquals(resp.status_code, WordAlreadyExistsException.status_code)

    def test_append_to_existing_entry(self):
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
        self.assertEquals(resp.status_code, 200)

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
            InvalidJsonReceivedException.status_code)

    def test_edit_entry(self):
        resp = requests.get(URL_HEAD + '/entry/jm/tehanu')
        data = resp.json()
        word_id = data[0]['id']
        resp = requests.put(
            URL_HEAD + '/entry/%d/edit' % word_id,
            json={
                'definitions': [{
                    'definition': 'tarameguni',
                    'definition_language': 'mg'
                }],
                'part_of_speech': 'aojs',
            }
        )
        self.assertEquals(resp.status_code, 200)

    def test_read_after_write_get_after_post(self):
        self.create_entry('nanaika', 'ka', 'ana', 'tarameguni', 'de')

        resp = requests.get(URL_HEAD + '/entry/ka/nanaika')
        data = resp.json()
        self.assertEquals(resp.status_code, 200)
        for datum in data:
            self.assertEquals(datum['word'], 'nanaika')
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

    def test_get_translation(self):
        self.create_entry('toki', 'tpo', 'ana', 'Sprach', 'de')
        self.create_entry('pona', 'tpo', 'ana', 'gut', 'de')
        self.create_entry('alks', 'tpo', 'ana', 'pals', 'fr')

        resp = requests.get(URL_HEAD + '/translations/tpo/de/toki')
        print(resp)
        j = resp.json()
        print(j)
        self.assertEquals(len(j), 1)
        self.assertEquals(resp.status_code, 200)

    def test_get_all_translations(self):
        self.create_entry('toki', 'tpo', 'ana', 'Sprach', 'de')
        self.create_entry('pona', 'tpo', 'ana', 'gut', 'de')

        resp = requests.get(URL_HEAD + '/translations/jm/tehanu')
        j = resp.json()
        self.assertEquals(len(j), 1)
        self.assertEquals(resp.status_code, 200)