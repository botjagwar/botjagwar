import copy
from unittest.case import TestCase

from api.model.word import Entry
from api.model.word import Translation


class TestEntry(TestCase):
    def test_to_tuple(self):
        entry = Entry(entry="1", part_of_speech="2", definitions=["3"], language="fr")
        self.assertEqual(entry.entry, "1")
        self.assertEqual(entry.part_of_speech, "2")
        self.assertEqual(entry.definitions, ["3"])

    def test_deep_copy(self):
        old = Entry(
            entry="tasumaki", part_of_speech="2", language="mg", definitions=["3"]
        )
        new = copy.deepcopy(old)
        new.entry = "wrong"
        new.definitions = ["potomaki"]
        self.assertNotEqual(new.entry, old.entry)
        self.assertNotEqual(new.definitions, old.definitions)

    def test_less_than(self):
        entry1 = Entry(entry="1", part_of_speech="2", language="kl", definitions=["3"])
        entry2 = Entry(entry="2", part_of_speech="2", language="km", definitions=["3"])

        self.assertLess(entry1, entry2)

    def test_less_than_2(self):
        entry1 = Entry(entry="a", part_of_speech="i", language="kk", definitions=["3"])
        entry2 = Entry(entry="b", part_of_speech="i", language="kk", definitions=["3"])

        self.assertLess(entry1, entry2)

    def test_less_than_3(self):
        entry1 = Entry(entry="1", part_of_speech="2", language="kl", definitions=["3"])
        entry2 = Entry(entry="1", part_of_speech="3", language="kl", definitions=["4"])

        self.assertLess(entry1, entry2)


class TestTranslation(TestCase):
    def test_serialise(self):
        translation = Translation(
            word="kaolak",
            language="kk",
            part_of_speech="ana",
            definition="alskdalskdalkas",
        )
        serialised = translation.serialise()
        self.assertEqual(serialised["word"], "kaolak")
        self.assertEqual(serialised["language"], "kk")
        self.assertEqual(serialised["part_of_speech"], "ana")
        self.assertEqual(serialised["definition"], "alskdalskdalkas")
