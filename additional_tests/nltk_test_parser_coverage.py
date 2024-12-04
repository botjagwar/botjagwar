import json
from copy import deepcopy
from unittest import TestCase

import nltk
from parameterized import parameterized

from api.parsers.phrase_parser import EnglishParser


def get_json_split_list():
    with open("test_data/test_parser_coverage.json", "r") as f:
        json_str = f.read()
        json_data = json.loads(json_str)
        split_list = []
        temp_list = []
        for e in json_data:
            print(e)
            temp_list.append(e)
            if len(temp_list) > 100:
                split_list.append((deepcopy(temp_list),))
                temp_list = []

        return split_list


split_list = get_json_split_list()


class TestPhraseCoverageParser(TestCase):

    def setUp(self):
        self.parser_object = EnglishParser()

    def tearDown(self):
        pass

    @parameterized.expand(split_list)
    def test_check_phrase_coverage(self, json_data):
        data = [d["definition"] for d in json_data]

        for d in data:
            if len(d) > 100:
                self.parser_object.abort += 1
                continue

            d = self.parser_object.preprocess(d)
            self.lp = 0
            tokens = nltk.word_tokenize(d)
            if len(tokens) < 2:
                continue

            print(tokens)
            self.parser_object.processed += 1
            pd = self.parser_object.process(d)
            self.parser_object.parsed += 1

        self.assertGreaterEqual(
            self.parser_object.parsed, 0.70 * len(json_data)
        )  # 70% coverage
