import json
import unittest

import aiohttp
from aiohttp.test_utils import make_mocked_request
from aiohttp.web import Response
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from api.dictionary.model import Word, Definition
from api.dictionary.request_handlers.entry import edit_entry, delete_entry

Base = declarative_base()


class TestEditEntry(unittest.TestCase):

    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:",
        )
        self.SessionClass = sessionmaker(bind=engine)
        self.session = self.SessionClass()
        self.app = {"session_instance": self.session}

    def tearDown(self):
        self.session.rollback()  # rollback changes made during testing
        self.session.close()  # close database session

    async def test_edit_entry(self):
        # create word to edit
        word = Word(word="test", language="en", part_of_speech="ana", definitions=[])
        self.session.add(word)
        self.session.commit()

        # create request with updated word data
        data = {
            "part_of_speech": "verb",
            "definitions": [
                {"definition": "an act of testing", "definition_language": "en"},
                {
                    "definition": "to make something undergo testing",
                    "definition_language": "en",
                },
            ],
        }
        request = make_mocked_request("PUT", "/words/1", json=data)

        # call edit_entry function with request
        response = await edit_entry(request)

        # assert that word has been updated in database and response is correct
        self.assertEqual(response.status, 200)
        word = self.session.query(Word).get(1)
        self.assertEqual(word.part_of_speech, "verb")
        self.assertEqual(len(word.definitions), 2)
        self.assertEqual(word.definitions[0].definition, "an act of testing")
        self.assertEqual(word.definitions[0].definition_language, "en")
        self.assertEqual(
            word.definitions[1].definition, "to make something undergo testing"
        )
        self.assertEqual(word.definitions[1].definition_language, "en")
        response_data = json.loads(response.text)
        self.assertEqual(response_data["id"], 1)
        self.assertEqual(response_data["text"], "test")
        self.assertEqual(response_data["part_of_speech"], "verb")
        self.assertEqual(len(response_data["definitions"]), 2)
        self.assertEqual(
            response_data["definitions"][0]["definition"], "an act of testing"
        )
        self.assertEqual(response_data["definitions"][0]["definition_language"], "en")
        self.assertEqual(
            response_data["definitions"][1]["definition"],
            "to make something undergo testing",
        )
        self.assertEqual(response_data["definitions"][1]["definition_language"], "en")


class TestDeleteEntry(unittest.TestCase):

    def setUp(self):
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        self.SessionClass = sessionmaker(bind=engine)
        self.session = self.SessionClass()
        self.app = {"session_instance": self.session}

    def tearDown(self):
        self.session.close()

    async def test_delete_entry_successfully(self):
        # Create a word and add it to the session
        word = Word(word="test", part_of_speech="noun")
        self.session.add(word)
        self.session.commit()

        # Delete the word
        response = await delete_entry(self.create_request(word.id))

        # Check that the word was deleted
        word = self.session.query(Word).filter_by(id=word.id).first()
        self.assertIsNone(word)

        # Check that the response has status code 204
        self.assertEqual(response.status, 204)

    async def test_delete_entry_with_dependent_definitions(self):
        # Create a word and some definitions and add them to the session
        word = Word(word="test", part_of_speech="noun")
        definition1 = Definition(definition="a trial or experiment", language="en")
        definition2 = Definition(
            definition="a procedure intended to establish the quality", language="en"
        )
        word.definitions.append(definition1)
        word.definitions.append(definition2)
        self.session.add(word)
        self.session.commit()

        # Delete the word with dependent definitions
        response = await delete_entry(
            self.create_request(word.id, delete_dependent_definitions=True)
        )

        # Check that the word was deleted
        word = self.session.query(Word).filter_by(id=word.id).first()
        self.assertIsNone(word)

        # Check that the dependent definitions were deleted
        definitions = self.session.query(Definition).all()
        self.assertEqual(len(definitions), 0)

        # Check that the response has status code 204
        self.assertEqual(response.status, 204)

    def create_request(self, word_id, delete_dependent_definitions=False):
        request = aiohttp.web.Request({}, None, None, None, None)
        request.match_info = {"word_id": str(word_id)}
        request.app = self.app
        request.query = {
            "delete_dependent_definitions": str(delete_dependent_definitions)
        }
        return request
