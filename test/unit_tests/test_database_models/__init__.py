from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock

from parameterized import parameterized

from api.dictionary.serialisers.json import Definition as DefinitionSerialiser, Word as WordSerialiser


def fixture_definition_2():
    definition_2 = MagicMock()
    definition_2.type = 'Definition'
    definition_2.id = 121298
    definition_2.date_changed = datetime(2013, 11, 12, 14, 30, 10)
    definition_2.definition = 'ity dia andrana fanonona iray'
    definition_2.definition_language = 'mg'
    definition_2.words = []
    definition_2.serialise.return_value = {
        "type": 'Definition',
        "id": 121298,
        "date_changed": datetime(2013, 11, 12, 14, 30, 10),
        "definition": 'ity dia andrana fanonona iray',
        "definition_language": 'mg',
    }

    return definition_2


def fixture_word_1():
    word_1 = MagicMock()
    word_1.type = "Word"
    word_1.id = 120
    word_1.date_changed = datetime(2022, 11, 12, 14, 30, 10)
    word_1.word = 'something_word1'
    word_1.language = 're'
    word_1.part_of_speech = 'ana'
    word_1.definitions = [fixture_definition_2(), fixture_definition_1()]
    return word_1


def fixture_word_2():
    word_2 = MagicMock()
    word_2.type = "Word"
    word_2.id = 12110
    word_2.date_changed = datetime(2024, 11, 12, 14, 30, 10)
    word_2.word = 'ssomething_word2'
    word_2.language = 'ree'
    word_2.part_of_speech = 'adv'
    word_2.definitions = [fixture_definition_2()]
    return word_2


def fixture_definition_1():
    definition_1 = MagicMock()
    definition_1.type = 'Definition'
    definition_1.id = 123456
    definition_1.date_changed = datetime(2019, 11, 12, 14, 30, 10)
    definition_1.definition = 'This is a test definition'
    definition_1.definition_language = 'en'
    definition_1.words = []
    definition_1.serialise.return_value = {
        'type': 'Definition',
        'id': 123456,
        'date_changed': datetime(2019, 11, 12, 14, 30, 10),
        'definition': 'This is a test definition',
        'definition_language': 'en',
    }
    return definition_1


word_1 = (fixture_word_1(),)
word_2 = (fixture_word_2(),)
definition_1 = (fixture_definition_1(),)
definition_2 = (fixture_definition_2(),)

definitions = [definition_1, definition_2]
words = [word_1, word_2]


class TestSerialiser(TestCase):
    @parameterized.expand(definitions)
    def test_definition_serialise(self, definition):
        serialiser = DefinitionSerialiser(definition)
        serialized = serialiser.serialise()
        print(serialized)
        self.assertEquals(serialized['id'], definition.id)
        self.assertEquals(
            serialized['last_modified'],
            definition.date_changed.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(serialized['definition'], definition.definition)
        self.assertEquals(
            serialized['language'],
            definition.definition_language)

    @parameterized.expand(definitions)
    def test_definition_serialise_with_words(self, definition):
        serialiser = DefinitionSerialiser(definition)
        serialized = serialiser.serialise_with_words()
        self.assertEquals(serialized['words'], definition.words)

    @parameterized.expand(words)
    def test_word_serialiser_serialise(self, word):
        serialiser = WordSerialiser(word)
        serialised = serialiser.serialise()
        for node in ['id', 'word', 'language', 'part_of_speech']:
            self.assertIn('definitions', serialised)
            self.assertEquals(serialised[node], getattr(word, node))

        self.assertIn('last_modified', serialised)
        self.assertEquals(
            serialised['last_modified'],
            word.date_changed.strftime("%Y-%m-%d %H:%M:%S"))

    @parameterized.expand(words)
    def test_word_serialiser_serialise_to_entry(self, word):
        serialiser = WordSerialiser(word)
        entry = serialiser.serialise_to_entry(['mg', 'en'])
        self.assertEquals(entry.entry, word.word)
        self.assertEquals(entry.part_of_speech, word.part_of_speech)
        self.assertEquals(
            entry.definitions, [
                d.definition for d in word.definitions])
        self.assertEquals(entry.language, word.language)

    @parameterized.expand(words)
    def test_word_serialiser_serialise_to_entry_one_definition(self, word):
        serialiser = WordSerialiser(word)
        entry = serialiser.serialise_to_entry(['mg'])
        self.assertEquals(entry.entry, word.word)
        self.assertEquals(entry.part_of_speech, word.part_of_speech)
        self.assertEquals(
            entry.definitions, [
                d.definition for d in word.definitions if d.definition_language == 'mg'])
        self.assertEquals(entry.language, word.language)

    @parameterized.expand(words)
    def test_word_serialiser_serialise_without_definition(self, word):
        serialiser = WordSerialiser(word)
        serialised = serialiser.serialise_without_definition()
        self.assertNotIn('definitions', serialised)
        for node in ['id', 'word', 'language', 'part_of_speech']:
            self.assertEquals(serialised[node], getattr(word, node))

        self.assertIn('last_modified', serialised)
        self.assertEquals(
            serialised['last_modified'],
            word.date_changed.strftime("%Y-%m-%d %H:%M:%S"))
