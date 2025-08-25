import configparser
import unittest
from copy import deepcopy

import pytest
from unittest.mock import Mock, MagicMock, patch

import pywikibot

from api.entryprocessor.wiki.base import WiktionaryProcessorException
from api.model.word import Entry
from api.translation_v2 import UntranslatedDefinition, TranslatedDefinition
from api.translation_v2.core import Translation
from api.translation_v2.exceptions import TranslationError

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


class TestPrepareTranslatedEntry:

    @pytest.fixture
    def translation_instance(self):
        """Create a properly configured Translation instance."""
        translation = Translation(use_configured_postprocessors=False)
        translation.working_wiki_language = "mg"
        return translation

    @pytest.fixture
    def mock_entry(self):
        """Create a mock entry with test data."""
        additional_data = {
            "reference": ["{{wikibolana|en|source}}"],
            "pronunciation": {"IPA": "/tɛst/"}
        }
        entry = Entry(
            entry="test_word", part_of_speech='ana', definitions=["original definition"],
            language="en", additional_data=additional_data
        )
        return entry

    @pytest.fixture
    def mock_wiktionary_processor(self):
        """Create a mock wiktionary processor."""
        processor = MagicMock()
        processor.language = "en"
        return processor

    def test_prepare_translated_entry(self, translation_instance, mock_entry, mock_wiktionary_processor):
        """Test that _prepare_translated_entry correctly prepares the entry."""
        # Patch the translate_additional_data method
        with patch.object(
                Translation,
                '_translate_additional_data',
                return_value={"reference": ["{{wikibolana|en|test}}"], "pronunciation": {"IPA": "/tɛst/"}}
        ) as mock_translate:
            # Call the method under test
            translated_definitions = ["translated definition"]
            result = translation_instance._prepare_translated_entry(
                mock_entry, translated_definitions, mock_wiktionary_processor
            )

            # Verify the method was called correctly
            mock_translate.assert_called_once_with(mock_entry, mock_wiktionary_processor)

            # Check that the result is as expected
            assert result is not mock_entry  # Should be a deepcopy
            assert result.entry == mock_entry.entry
            assert result.language == mock_entry.language
            assert result.part_of_speech == mock_entry.part_of_speech
            assert result.definitions == translated_definitions
            assert result.additional_data == {"reference": ["{{wikibolana|en|test}}"],
                                              "pronunciation": {"IPA": "/tɛst/"}}

    def test_translate_additional_data(self, translation_instance, mock_entry, mock_wiktionary_processor):
        """Test that _translate_additional_data correctly processes additional data."""
        with patch("api.translation_v2.core.translate_references",
                   return_value=["{{wikibolana|en|source}}"]) as mock_refs, \
                patch("api.translation_v2.core.translate_pronunciation", return_value={"IPA": "/tɛst/"}) as mock_pron, \
                patch("api.translation_v2.core.filter_additional_data",
                      return_value={"reference": ["{{wikibolana|en|source}}"],
                                    "pronunciation": {"IPA": "/tɛst/"}}) as mock_filter:
            # Call the method under test
            result = translation_instance._translate_additional_data(mock_entry, mock_wiktionary_processor)

            # Verify the methods were called correctly
            mock_refs.assert_called_once_with(
                mock_entry.additional_data["reference"],
                source="en",
                target="mg",
                use_postgrest="automatic"
            )
            mock_pron.assert_called_once_with(mock_entry.additional_data["pronunciation"])
            mock_filter.assert_called_once()

            # Check that the result is as expected
            assert result == {"reference": ["{{wikibolana|en|source}}"], "pronunciation": {"IPA": "/tɛst/"}}

    def test_translate_additional_data_empty(self, translation_instance, mock_wiktionary_processor):
        """Test _translate_additional_data with an entry without additional data."""
        entry = Entry(
            entry="test_word", part_of_speech='ana', definitions=["original definition"],
            language="en", additional_data=None
        )

        with patch("api.translation_v2.core.filter_additional_data", return_value={}) as mock_filter:
            result = translation_instance._translate_additional_data(entry, mock_wiktionary_processor)

            mock_filter.assert_called_once_with({})
            assert result == {}

    def test_translate_additional_data_partial(self, translation_instance, mock_wiktionary_processor):
        """Test _translate_additional_data with an entry containing only some additional data fields."""
        entry = Entry(
            entry="test_word", part_of_speech='ana', definitions=["original definition"],
            language="en", additional_data={"other_field": "value"}
        )

        with patch("api.translation_v2.core.filter_additional_data",
                   return_value={"other_field": "value"}) as mock_filter:
            result = translation_instance._translate_additional_data(entry, mock_wiktionary_processor)

            mock_filter.assert_called_once_with({"other_field": "value"})
            assert result == {"other_field": "value"}

    def test_apply_translation_methods(self, translation_instance, mock_entry, mock_wiktionary_processor):
        """Test _apply_translation_methods with successful and unsuccessful translations."""
        definition = "test definition"

        # Test successful translation
        with patch('api.translation_v2.core.translation_methods', [
            (MagicMock(return_value=TranslatedDefinition("translated definition")), True)
        ]):
            result = translation_instance._apply_translation_methods(
                definition, mock_entry, mock_wiktionary_processor
            )

            # Check result
            assert result == "translated definition"

        # Test no successful translation
        with patch('api.translation_v2.core.translation_methods', [
            (MagicMock(return_value=UntranslatedDefinition("untranslated")), False)
        ]):
            result = translation_instance._apply_translation_methods(
                definition, mock_entry, mock_wiktionary_processor
            )

            # Check result
            assert result is None

    def test_remove_templates(self, translation_instance, mock_entry, mock_wiktionary_processor):
        """Test _remove_templates with successful and failed refinements."""
        definition = "{{template}} definition"

        # Test successful refinement
        mock_wiktionary_processor.refine_definition.return_value = ["refined definition"]

        result = translation_instance._remove_templates(
            definition, mock_entry, mock_wiktionary_processor
        )

        # Check result and method calls
        assert result == "refined definition"
        mock_wiktionary_processor.refine_definition.assert_called_with(
            definition, part_of_speech=mock_entry.part_of_speech, remove_all_templates=True
        )

        # Test failed refinement
        mock_wiktionary_processor.refine_definition.return_value = []

        result = translation_instance._remove_templates(
            definition, mock_entry, mock_wiktionary_processor
        )

        # Check that empty definition is returned
        assert result == ''

    def test_refine_definitions_success(self, translation_instance, mock_entry, mock_wiktionary_processor):
        """Test _refine_definitions when refining is successful."""
        # Setup
        definition_line = "original test definition"
        mock_wiktionary_processor.refine_definition.return_value = ["refined definition 1", "refined definition 2"]

        # Call the method under test
        result = translation_instance._refine_definitions(definition_line, mock_entry, mock_wiktionary_processor)

        # Assertions
        mock_wiktionary_processor.refine_definition.assert_called_once_with(
            definition_line, part_of_speech=mock_entry.part_of_speech
        )
        assert result == ["refined definition 1", "refined definition 2"]

    def test_refine_definitions_exception(self, translation_instance, mock_entry, mock_wiktionary_processor):
        """Test _refine_definitions when refining raises an exception."""
        # Setup
        definition_line = "problematic definition"
        mock_wiktionary_processor.refine_definition.side_effect = WiktionaryProcessorException(
            "Error refining definition")

        # Call the method under test
        result = translation_instance._refine_definitions(definition_line, mock_entry, mock_wiktionary_processor)

        # Assertions
        mock_wiktionary_processor.refine_definition.assert_called_once_with(
            definition_line, part_of_speech=mock_entry.part_of_speech
        )
        assert result == []


    def test_translate_entry_definitions_no_definitions(self, translation_instance, mock_entry,
                                                        mock_wiktionary_processor):
        """Test with an entry that has no definitions."""
        # Setup
        mock_entry.definitions = []

        # Call the method
        result = translation_instance._translate_entry_definitions(mock_entry, mock_wiktionary_processor)

        # Assertions
        assert result == []

    def test_translate_wiktionary_page(self, translation_instance, mock_wiktionary_processor):
        """Test the translate_wiktionary_page method."""
        # Setup - Create mock entries returned by the processor
        entry1 = Entry(
            entry="word1",
            part_of_speech="noun",
            definitions=["definition1"],
            language="en",
            additional_data={"reference": ["ref1"]}
        )
        entry2 = Entry(
            entry="word2",
            part_of_speech="verb",
            definitions=["definition2"],
            language="en",
            additional_data={"pronunciation": {"IPA": "/word2/"}}
        )
        mock_entries = [entry1, entry2]

        # Configure mock wiktionary processor
        mock_wiktionary_processor.get_all_entries.return_value = mock_entries
        mock_wiktionary_processor.language = "en"
        mock_wiktionary_processor.title = "test_page"

        # Configure patched methods
        with patch.object(translation_instance, '_translate_entry_definitions') as mock_translate_defs, \
                patch.object(translation_instance, '_prepare_translated_entry') as mock_prepare, \
                patch.object(translation_instance, '_postprocess_entries') as mock_postprocess:
            # Set up method behaviors
            mock_translate_defs.side_effect = [
                ["translated_def1"],  # For entry1
                []  # For entry2 (no successful translations)
            ]

            translated_entry1 = deepcopy(entry1)
            translated_entry1.definitions = ["translated_def1"]
            mock_prepare.return_value = translated_entry1

            final_entry = deepcopy(translated_entry1)
            mock_postprocess.return_value = [final_entry]

            # Call the method
            result = translation_instance.translate_wiktionary_page(mock_wiktionary_processor)

            # Assertions
            assert len(result) == 1  # Only one entry was successfully translated
            assert result[0].entry == "word1"
            assert result[0].definitions == ["translated_def1"]

            # Verify method calls
            mock_wiktionary_processor.get_all_entries.assert_called_once_with(
                get_additional_data=True,
                translate_definitions_to_malagasy=True,
                human_readable_form_of_definition=True
            )
            assert mock_translate_defs.call_count == 2
            mock_prepare.assert_called_once_with(entry1, ["translated_def1"], mock_wiktionary_processor)
            mock_postprocess.assert_called_once_with([translated_entry1], mock_wiktionary_processor)

    def test_get_single_word_definitions(self, translation_instance, mock_wiktionary_processor):
        """Test the get_single_word_definitions method."""
        # Setup
        language = "en"
        definition = "test_word"
        part_of_speech = "noun"

        # Create mock entry
        mock_entry = Entry(
            entry="test_word",
            part_of_speech=part_of_speech,
            definitions=["definition1", "another definition"],
            language=language,
            additional_data={}
        )

        # Setup mocks
        with patch('api.translation_v2.core.entryprocessor.WiktionaryProcessorFactory.create') as mock_factory, \
                patch('api.translation_v2.core.Page') as mock_page, \
                patch('api.translation_v2.core.Site') as mock_site:
            # Setup factory mock to return our processor
            mock_factory.return_value = MagicMock(return_value=mock_wiktionary_processor)

            # Configure processor
            mock_wiktionary_processor.get_all_entries.return_value = [
                mock_entry,
                Entry(entry="test_word", part_of_speech="verb", definitions=["verb definition"], language=language),
                Entry(entry="test_word", part_of_speech=part_of_speech, definitions=["definition2"], language="fr")
            ]

            # Configure refine_definition responses
            mock_wiktionary_processor.refine_definition.side_effect = [
                ["refined definition1"],
                WiktionaryProcessorException("Error refining"),
                ["refined definition2"]
            ]

            # Call the method
            result = translation_instance.get_single_word_definitions(definition, language, part_of_speech)

            # Assertions
            assert len(result) == 1
            assert "refined definition1" in result

            # Verify calls
            mock_site.assert_called_once_with(language, "wiktionary")
            mock_page.assert_called_once()
            mock_wiktionary_processor.process.assert_called_once()
            mock_wiktionary_processor.get_all_entries.assert_called_once_with(
                get_additional_data=True, cleanup_definitions=True, advanced=True
            )
            assert mock_wiktionary_processor.refine_definition.call_count == 2


class TestProcessWiktionaryWikiPage:

    @pytest.fixture
    def translation_instance(self):
        """Create a Translation instance with mocks."""
        translation = Translation()
        translation.default_publisher = MagicMock()
        translation.output = MagicMock()
        translation._save_translation_from_page = MagicMock()
        translation.publish_translated_references = MagicMock()
        return translation

    @pytest.fixture
    def mock_wiki_page(self):
        """Create a mock pywikibot.Page object."""
        wiki_page = MagicMock(spec=pywikibot.Page)
        wiki_page.title.return_value = "Test Page"
        wiki_page.namespace.return_value.content = True
        wiki_page.site.lang = "en"
        return wiki_page

    def test_process_wiktionary_wiki_page_processor_creation_exception(self, translation_instance, mock_wiki_page):
        """Test handling of exception during WiktionaryProcessor creation."""
        with patch('api.translation_v2.core.entryprocessor.WiktionaryProcessorFactory.create') as mock_factory:
            # Setup mock to raise an exception
            mock_factory.side_effect = Exception("Failed to create processor")

            # Call the method
            result = translation_instance.process_wiktionary_wiki_page(mock_wiki_page)

            # Assertions
            assert result is None
            mock_factory.assert_called_once_with("en")

    def test_process_wiktionary_wiki_page_set_text_exception(self, translation_instance, mock_wiki_page):
        """Test handling of exception when setting text."""
        with patch('api.translation_v2.core.entryprocessor.WiktionaryProcessorFactory.create') as mock_factory, \
                patch.object(mock_wiki_page, 'get') as mock_get, \
                patch.object(mock_wiki_page, 'isRedirectPage', return_value=False):
            # Setup mocks
            mock_processor = MagicMock()
            mock_factory.return_value = MagicMock(return_value=mock_processor)
            mock_get.side_effect = Exception("Failed to get page content")

            # Call the method
            result = translation_instance.process_wiktionary_wiki_page(mock_wiki_page)

            # Assertions
            assert result is None
            mock_processor.set_text.assert_not_called()

    def test_process_wiktionary_wiki_page_invalid_redirect(self, translation_instance, mock_wiki_page):
        """Test handling of InvalidTitleError during redirect."""
        mock_wiki_page.isRedirectPage.return_value = True

        with patch.object(mock_wiki_page, 'getRedirectTarget') as mock_get_target:
            # Setup mock to raise an exception
            mock_get_target.side_effect = pywikibot.exceptions.InvalidTitleError("Invalid title")

            # Call the method
            result = translation_instance.process_wiktionary_wiki_page(mock_wiki_page)

            # Assertions
            assert result is None
            mock_get_target.assert_called_once()

    def test_process_wiktionary_wiki_page_unexpected_exception(self, translation_instance, mock_wiki_page):
        """Test handling of unexpected exceptions during processing."""
        with patch('api.translation_v2.core.entryprocessor.WiktionaryProcessorFactory.create') as mock_factory, \
                patch.object(mock_wiki_page, 'get') as mock_get, \
                patch.object(mock_wiki_page, 'isRedirectPage', return_value=False), \
                patch.object(translation_instance, 'translate_wiktionary_page') as mock_translate:
            # Setup mocks
            mock_get.return_value = "page content"
            mock_processor = MagicMock()
            mock_factory.return_value = MagicMock(return_value=mock_processor)
            mock_translate.side_effect = Exception("Unexpected error")

            # Call the method
            result = translation_instance.process_wiktionary_wiki_page(mock_wiki_page)

            # Assertions
            assert result == 0
            mock_translate.assert_called_once_with(mock_processor)

    def test_process_wiktionary_wiki_page_custom_publish_function(self, translation_instance, mock_wiki_page):
        """Test using a custom publish function."""
        custom_publish = MagicMock()

        with patch('api.translation_v2.core.entryprocessor.WiktionaryProcessorFactory.create') as mock_factory, \
                patch.object(translation_instance, 'translate_wiktionary_page') as mock_translate, \
                patch.object(mock_wiki_page, 'get') as mock_get, \
                patch.object(mock_wiki_page, 'isRedirectPage', return_value=False):
            # Setup mocks
            mock_get.return_value = "page content"
            mock_processor = MagicMock()
            mock_factory.return_value = MagicMock(return_value=mock_processor)
            mock_entries = [MagicMock()]
            mock_translate.return_value = mock_entries

            # Call the method with custom publish function
            result = translation_instance.process_wiktionary_wiki_page(mock_wiki_page,
                                                                       custom_publish_function=custom_publish)

            # Assertions
            assert result == 1
            translation_instance.default_publisher.publish_to_wiktionary.assert_not_called()
            custom_publish.assert_called_once_with(page_title="Test Page", entries=mock_entries)


class TestPostprocessorMethods:

    @pytest.fixture
    def mock_entries(self):
        """Create mock entries for testing."""
        return [
            Entry(
                entry="word1",
                part_of_speech="noun",
                definitions=["definition1"],
                language="en",
                additional_data={"reference": ["ref1"]}
            ),
            Entry(
                entry="word2",
                part_of_speech="verb",
                definitions=["definition2"],
                language="fr",
                additional_data={"pronunciation": {"IPA": "/word2/"}}
            )
        ]

    @pytest.fixture
    def static_translation(self):
        """Create a Translation instance with static postprocessors."""
        translation = Translation(use_configured_postprocessors=False)
        translation._post_processors = []
        return translation

    @pytest.fixture
    def dynamic_translation(self):
        """Create a Translation instance with dynamic postprocessors."""
        translation = Translation(use_configured_postprocessors=True)
        translation.load_postprocessors = MagicMock()
        return translation

    def test_run_postprocessors_static(self, static_translation, mock_entries):
        """Test running static postprocessors."""
        with patch.object(static_translation, '_run_static_postprocessors') as mock_static:
            mock_static.return_value = mock_entries
            result = static_translation.run_postprocessors(mock_entries)

            mock_static.assert_called_once_with(mock_entries)
            assert result == mock_entries

    def test_run_postprocessors_dynamic(self, dynamic_translation, mock_entries):
        """Test running dynamic postprocessors."""
        with patch.object(dynamic_translation, '_run_dynamic_postprocessors') as mock_dynamic:
            mock_dynamic.return_value = mock_entries
            result = dynamic_translation.run_postprocessors(mock_entries)

            mock_dynamic.assert_called_once_with(mock_entries)
            assert result == mock_entries

    def test_check_post_processor_output_valid(self, static_translation, mock_entries):
        """Test validation with valid entries."""
        result = static_translation._check_post_processor_output(mock_entries)
        assert result == mock_entries

    def test_check_post_processor_output_not_list(self, static_translation):
        """Test validation with non-list output."""
        with pytest.raises(TranslationError, match="Post-processors must return list"):
            static_translation._check_post_processor_output("not a list")

    def test_check_post_processor_output_invalid_items(self, static_translation):
        """Test validation with list containing non-Entry objects."""
        with pytest.raises(TranslationError, match="Post-processors return list elements must all be of type Entry"):
            static_translation._check_post_processor_output([1, 2, 3])

    def test_run_static_postprocessors_empty(self, static_translation, mock_entries):
        """Test with no static postprocessors."""
        static_translation._post_processors = []
        result = static_translation._run_static_postprocessors(mock_entries)
        assert result == mock_entries

    def test_run_static_postprocessors_not_list(self, static_translation, mock_entries):
        """Test with non-list postprocessors."""
        static_translation._post_processors = "not a list"
        with pytest.raises(TranslationError, match="post processor must be a list"):
            static_translation._run_static_postprocessors(mock_entries)

    def test_run_static_postprocessors_valid(self, static_translation, mock_entries):
        """Test with valid static postprocessors."""

        # Create mock postprocessors
        def processor1(entries):
            for entry in entries:
                entry.definitions = [f"{d}_processed1" for d in entry.definitions]
            return entries

        def processor2(entries):
            for entry in entries:
                entry.definitions = [f"{d}_processed2" for d in entry.definitions]
            return entries

        static_translation._post_processors = [processor1, processor2]

        result = static_translation._run_static_postprocessors(mock_entries)

        assert result[0].definitions == ["definition1_processed1_processed2"]
        assert result[1].definitions == ["definition2_processed1_processed2"]

    def test_run_dynamic_postprocessors_no_config(self, dynamic_translation, mock_entries):
        """Test dynamic postprocessors with no configuration."""
        dynamic_translation.load_postprocessors.return_value = []

        result = dynamic_translation._run_dynamic_postprocessors(mock_entries)

        assert result == mock_entries
        assert dynamic_translation.load_postprocessors.call_count == 2

    def test_run_dynamic_postprocessors_with_config(self, dynamic_translation, mock_entries):
        """Test dynamic postprocessors with configuration."""

        # Mock postprocessor functions
        def mock_pp1(*args):
            def process(entries):
                for entry in entries:
                    entry.definitions = [f"{d}_pp1" for d in entry.definitions]
                return entries

            return process

        def mock_pp2(*args):
            def process(entries):
                for entry in entries:
                    entry.definitions = [f"{d}_pp2" for d in entry.definitions]
                return entries

            return process

        # Configure load_postprocessors to return different configs for each entry
        dynamic_translation.load_postprocessors.side_effect = [
            [("pp1", ("arg1",)), ("pp2", ("arg2",))],  # For first entry
            []  # For second entry
        ]

        # Mock the postprocessors module
        with patch("api.translation_v2.core.postprocessors") as postprocessors_mock:
            postprocessors_mock.pp1 = mock_pp1
            postprocessors_mock.pp2 = mock_pp2
            result = dynamic_translation._run_dynamic_postprocessors(mock_entries)

            # First entry should be processed
            assert result[0].definitions == ["definition1_pp1_pp2"]
            # Second entry should remain unchanged
            assert result[1].definitions == ["definition2"]

            # Check that load_postprocessors was called correctly
            dynamic_translation.load_postprocessors.assert_any_call("en", "noun")
            dynamic_translation.load_postprocessors.assert_any_call("fr", "verb")

    def test_run_dynamic_postprocessors_with_exception(self, dynamic_translation, mock_entries):
        """Test dynamic postprocessors with an exception."""

        # Mock a postprocessor that raises an exception
        def mock_failing_pp(*args):
            def process(entries):
                raise ValueError("Processing error")

            return process

        dynamic_translation.load_postprocessors.return_value = [("failing_pp", ())]

        # Mock the postprocessors module and the log
        with patch("api.translation_v2.core.postprocessors") as postprocessors_mock, \
                patch("api.translation_v2.core.log") as mock_log:
            postprocessors_mock.failing_pp = mock_failing_pp

            with pytest.raises(ValueError):
                result = dynamic_translation._run_dynamic_postprocessors([mock_entries[0]])

                # Entry should remain unchanged
                assert result == [mock_entries[0]]
                # Exception should be logged
                mock_log.exception.assert_called_once()


class TestCreateOrRenameTemplateOnTargetWiki:

    @pytest.fixture
    def translation_instance(self):
        """Create a Translation instance."""
        return Translation(use_configured_postprocessors=False)

    @patch('api.translation_v2.core.Site')
    @patch('api.translation_v2.core.Page')
    @patch('api.translation_v2.core.log')
    def test_existing_source_nonexisting_target(self, mock_log, MockPage, MockSite, translation_instance):
        """Test when source template exists and target doesn't."""
        # Set up mocks
        mock_source_wiki = MagicMock()
        mock_target_wiki = MagicMock()
        mock_target_wiki.wiki = "mg"

        MockSite.side_effect = [mock_source_wiki, mock_target_wiki]

        # Mock the three pages (source, redirect, target)
        mock_source_page = MagicMock()
        mock_redirect_page = MagicMock()
        mock_target_page = MagicMock()

        MockPage.side_effect = [mock_source_page, mock_redirect_page, mock_target_page]

        # Configure page behaviors
        mock_source_page.exists.return_value = True
        mock_source_page.isRedirectPage.return_value = False
        mock_source_page.get.return_value = "Template content"
        mock_source_page.title.return_value = "Template:SourceName"

        mock_target_page.exists.return_value = False
        mock_target_page.title.return_value = "Endrika:TargetName"

        mock_redirect_page.exists.return_value = False

        # Execute the method
        translation_instance.create_or_rename_template_on_target_wiki(
            "en", "SourceName", "mg", "TargetName"
        )

        # Verify interactions
        MockSite.assert_any_call("en", "wiktionary")
        MockSite.assert_any_call("mg", "wiktionary")

        MockPage.assert_any_call(mock_source_wiki, "Template:SourceName")
        MockPage.assert_any_call(mock_target_wiki, "Endrika:SourceName")
        MockPage.assert_any_call(mock_target_wiki, "Endrika:TargetName")

        mock_target_page.put.assert_called_once_with(
            "Template content",
            "Pejy noforonina tamin'ny « Template content »"
        )
        mock_redirect_page.put.assert_called_once_with(
            f"#FIHODINANA [[{mock_target_page.title()}]]",
            "mametra-pihodinana"
        )
        mock_log.info.assert_called_once()

    @patch('api.translation_v2.core.Site')
    @patch('api.translation_v2.core.Page')
    def test_existing_source_existing_target(self, MockPage, MockSite, translation_instance):
        """Test when both source and target templates exist."""
        # Set up mocks
        mock_source_wiki = MagicMock()
        mock_target_wiki = MagicMock()
        MockSite.side_effect = [mock_source_wiki, mock_target_wiki]

        mock_source_page = MagicMock()
        mock_redirect_page = MagicMock()
        mock_target_page = MagicMock()
        MockPage.side_effect = [mock_source_page, mock_redirect_page, mock_target_page]

        # Configure page behaviors
        mock_source_page.exists.return_value = True
        mock_source_page.isRedirectPage.return_value = False

        mock_target_page.exists.return_value = True

        mock_redirect_page.exists.return_value = False

        # Execute the method
        translation_instance.create_or_rename_template_on_target_wiki(
            "en", "SourceName", "mg", "TargetName"
        )

        # Verify interactions
        mock_target_page.put.assert_not_called()
        mock_redirect_page.put.assert_called_once()

    @patch('api.translation_v2.core.Site')
    @patch('api.translation_v2.core.Page')
    def test_redirect_source(self, MockPage, MockSite, translation_instance):
        """Test when source template is a redirect."""
        # Set up mocks
        mock_source_wiki = MagicMock()
        mock_target_wiki = MagicMock()
        MockSite.side_effect = [mock_source_wiki, mock_target_wiki]

        mock_source_page = MagicMock()
        MockPage.return_value = mock_source_page

        # Configure page behaviors
        mock_source_page.exists.return_value = True
        mock_source_page.isRedirectPage.return_value = True

        # Execute the method
        translation_instance.create_or_rename_template_on_target_wiki(
            "en", "SourceName", "mg", "TargetName"
        )

        # Verify no page creation occurred
        mock_source_page.put.assert_not_called()

    @patch('api.translation_v2.core.Site')
    @patch('api.translation_v2.core.Page')
    def test_nonexistent_source(self, MockPage, MockSite, translation_instance):
        """Test when source template doesn't exist."""
        # Set up mocks
        mock_source_wiki = MagicMock()
        mock_target_wiki = MagicMock()
        MockSite.side_effect = [mock_source_wiki, mock_target_wiki]

        mock_source_page = MagicMock()
        MockPage.return_value = mock_source_page

        # Configure page behaviors
        mock_source_page.exists.return_value = False

        # Execute the method
        translation_instance.create_or_rename_template_on_target_wiki(
            "en", "SourceName", "mg", "TargetName"
        )

        # Verify no page creation occurred
        mock_source_page.put.assert_not_called()

    @patch('api.translation_v2.core.Site')
    @patch('api.translation_v2.core.Page')
    def test_template_name_formatting(self, MockPage, MockSite, translation_instance):
        """Test template name formatting with braces."""
        # Set up mocks
        mock_source_wiki = MagicMock()
        mock_target_wiki = MagicMock()
        MockSite.side_effect = [mock_source_wiki, mock_target_wiki]

        # Execute the method with template names containing braces
        translation_instance.create_or_rename_template_on_target_wiki(
            "en", "{{SourceName}}", "mg", "{{TargetName}}"
        )

        # Verify correct page titles were created
        MockPage.assert_any_call(mock_source_wiki, "Template:SourceName")
        MockPage.assert_any_call(mock_target_wiki, "Endrika:SourceName")
        MockPage.assert_any_call(mock_target_wiki, "Endrika:TargetName")
