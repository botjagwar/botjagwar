import configparser
import unittest
from unittest.mock import MagicMock, Mock

from api.translation_v2.core import Translation, Entry

page_content = """
=={{=de=}}==

{{-mpam-|de}}
'''weit''' 
# [[be]]

{{-fanononana-}}
* {{IPA|de|/vaɪ̯t/}}
* {{audio|de|De-weit.ogg|audio}}
* {{audio|de|De-weit2.ogg|audio}}
* {{audio|de|De-at-weit.ogg|audio (Austria)}}

{{-tsiahy-}}
* {{R:Duden}}
"""


class TestTranslationStaticMethods(unittest.TestCase):

    def test_add_wiktionary_credit(self):
        # Create a mock pywikibot.Page object for testing purposes
        wiki_page = MagicMock()
        wiki_page.language = "en"
        wiki_page.title = "Test Page"

        # Create some sample input entries
        entries = [
            Entry(
                entry="cat",
                definitions=["chat"],
                part_of_speech="ana",
                language="en",
                additional_data=None,
            ),
            Entry(
                entry="dog",
                definitions=["chien"],
                part_of_speech="ana",
                language="en",
                additional_data={"reference": ["test"]},
            ),
        ]

        # Call the method being tested
        out_entries = Translation.add_wiktionary_credit(entries, wiki_page)

        # Check that the output has the expected length
        self.assertEqual(len(out_entries), 2)

        # Check that the additional_data field of the first output entry has been updated correctly
        expected_reference = "{{wikibolana|en|Test Page}}"
        self.assertIn("reference", out_entries[0].additional_data)
        self.assertIsInstance(out_entries[0].additional_data["reference"], list)
        self.assertIn(expected_reference, out_entries[0].additional_data["reference"])

        # Check that the additional_data field of the second output entry has been updated correctly
        self.assertIn("reference", out_entries[1].additional_data)
        self.assertIsInstance(out_entries[1].additional_data["reference"], list)
        self.assertEqual(len(out_entries[1].additional_data["reference"]), 2)
        self.assertIn("test", out_entries[1].additional_data["reference"])
        self.assertIn(expected_reference, out_entries[1].additional_data["reference"])

    def test_generate_summary_from_added_entries(self):
        # Create some sample input entries
        entries = [
            Entry(
                entry="chat",
                part_of_speech="ana",
                definitions=["cat"],
                language="fr",
                additional_data=None,
            ),
            Entry(
                entry="chien",
                part_of_speech="ana",
                definitions=["dog"],
                language="fr",
                additional_data=None,
            ),
            Entry(
                entry="pomme",
                part_of_speech="ana",
                definitions=["apple"],
                language="fr",
                additional_data=None,
            ),
            Entry(
                entry="apple",
                part_of_speech="ana",
                definitions=["pomme"],
                language="en",
                additional_data=None,
            ),
            Entry(
                entry="book",
                part_of_speech="ana",
                definitions=["livre"],
                language="en",
                additional_data=None,
            ),
            Entry(
                entry="livre",
                part_of_speech="ana",
                definitions=["book"],
                language="fr",
                additional_data=None,
            ),
        ]

        # Call the method being tested
        summary = Translation._generate_summary_from_added_entries(entries)

        # Check that the summary has the expected format and content
        self.assertEqual(summary, "Dikanteny: en, fr")

        # Create a different set of input entries with only one language represented
        entries = [
            Entry(
                entry="chat",
                part_of_speech="ana",
                definitions=["cat"],
                language="fr",
                additional_data=None,
            ),
            Entry(
                entry="chien",
                part_of_speech="ana",
                definitions=["dog"],
                language="fr",
                additional_data=None,
            ),
            Entry(
                entry="pomme",
                part_of_speech="ana",
                definitions=["apple"],
                language="fr",
                additional_data=None,
            ),
        ]

        # Call the method again with the new input entries
        summary = Translation._generate_summary_from_added_entries(entries)

        # Check that the summary has the expected format and content in this case as well
        self.assertEqual(summary, "Dikanteny: fr")


class TestGenerateSummary(unittest.TestCase):

    def setUp(self):
        self.target_page_mock = Mock()
        self.target_page_mock.exists.return_value = True
        self.target_page_mock.isRedirectPage.return_value = False
        self.target_page_mock.get.return_value = "old content"

        self.config_mock = Mock()
        self.config_mock.get.return_value = "1"

        self.entries = [
            Entry(
                entry="chat",
                part_of_speech="ana",
                definitions=["cat"],
                language="fr",
                additional_data=None,
            ),
            Entry(
                entry="chien",
                part_of_speech="ana",
                definitions=["dog"],
                language="fr",
                additional_data=None,
            ),
            Entry(
                entry="pomme",
                part_of_speech="ana",
                definitions=["apple"],
                language="fr",
                additional_data=None,
            ),
        ]
        self.content_mock = "new content"

        self.obj = Translation()
        self.obj.config = self.config_mock

    def test_ninja_mode_1_target_page_exists_content_greater_than_125_percent_of_old_content(
        self,
    ):
        self.config_mock.get.return_value = "1"
        result = self.obj.generate_summary(
            self.entries,
            self.target_page_mock,
            2 * self.target_page_mock.get.return_value[::-1],
        )

        self.assertEqual(result, "nanitatra")

    def test_ninja_mode_1_target_page_exists_content_less_than_or_equal_to_125_percent_of_old_content(
        self,
    ):
        self.config_mock.get.return_value = "1"
        result = self.obj.generate_summary(
            self.entries,
            self.target_page_mock,
            self.target_page_mock.get.return_value[::-1],
        )

        self.assertEqual(result, "nanitsy")

    def test_ninja_mode_1_target_page_does_not_exist_and_content_greater_than_200(self):
        self.config_mock.get.return_value = "1"
        self.target_page_mock.exists.return_value = False
        result = self.obj.generate_summary(
            self.entries, self.target_page_mock, 2 * page_content
        )
        self.assertNotEqual(result.find("..."), -1)

    def test_ninja_mode_1_target_page_does_not_exist_and_content_less_than_or_equal_to_200(
        self,
    ):
        self.config_mock.get.return_value = "1"
        self.target_page_mock.exists.return_value = False
        result = self.obj.generate_summary(
            self.entries, self.target_page_mock, page_content[:200]
        )

        self.assertEqual(result, f"Pejy noforonina tamin'ny « {page_content[:200]} »")

    def test_ninja_mode_other_than_1(self):
        self.config_mock.get.return_value = "other"
        result = self.obj.generate_summary(
            self.entries, self.target_page_mock, self.content_mock
        )
        self.assertEqual(
            result, self.obj._generate_summary_from_added_entries(self.entries)
        )


class TestLoadPostprocessors(unittest.TestCase):

    def setUp(self):
        self.config_mock = Mock()
        self.language = "en"
        self.part_of_speech = "ana"

        self.obj = Translation()
        self.obj.postprocessors_config = Mock()
        self.obj.config = Mock()

    def test_no_sections_exist(self):
        self.obj.postprocessors_config.specific_config_parser.options.side_effect = (
            configparser.NoSectionError("section not found")
        )
        result = self.obj.load_postprocessors(self.language, self.part_of_speech)
        self.assertEqual([], result)

    def test_language_section_exists(self):
        self.obj.postprocessors_config.specific_config_parser.options.side_effect = None
        self.obj.postprocessors_config.specific_config_parser.options.return_value = [
            "postprocessor_1",
            "postprocessor_2",
        ]
        self.obj.postprocessors_config.specific_config_parser.get.return_value = (
            "arg1,arg2"
        )
        result = self.obj.load_postprocessors(self.language, self.part_of_speech)
        expected = [
            ("postprocessor_1", ("arg1", "arg2")),
            ("postprocessor_2", ("arg1", "arg2")),
        ]
        self.obj.postprocessors_config.specific_config_parser.get.assert_any_call(
            f"{self.language}:{self.part_of_speech}", "postprocessor_1"
        )
        self.obj.postprocessors_config.specific_config_parser.get.assert_any_call(
            f"{self.language}:{self.part_of_speech}", "postprocessor_2"
        )

    def test_pos_specific_section_exists(self):
        self.obj.postprocessors_config.options.side_effect = [
            configparser.NoSectionError("section not found"),
            ["postprocessor_3"],
        ]
        self.obj.postprocessors_config.specific_config_parser.options.return_value = [
            "postprocessor_3"
        ]
        self.obj.postprocessors_config.specific_config_parser.get.return_value = (
            "arg3,arg4"
        )
        result = self.obj.load_postprocessors(self.language, self.part_of_speech)
        expected = [("postprocessor_3", ("arg3", "arg4"))]
        self.assertEqual(result, expected)
        self.obj.postprocessors_config.specific_config_parser.options.assert_any_call(
            self.language
        )
        self.obj.postprocessors_config.specific_config_parser.options.assert_any_call(
            f"{self.language}:{self.part_of_speech}"
        )
