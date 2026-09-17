from unittest.mock import MagicMock, patch

import pytest
from api.entryprocessor.wiki.base import WiktionaryProcessorException
from api.model.word import Entry
from api.translation_v2.core import Translation


@pytest.fixture
def mock_translation():
    return Translation()


@pytest.fixture
def mock_wiktionary_processor():
    return MagicMock()


@pytest.fixture
def mock_definitions():
    class MockDefinitions:
        part_of_speech = "noun"
        lemma = "test_lemma"

    return MockDefinitions()


def test_create_lemma_if_not_exists_lemma_exists(mock_translation, mock_wiktionary_processor, mock_definitions, mocker):
    mock_translation.check_if_page_exists = MagicMock(return_value=True)
    with patch("api.translation_v2.core.already_visited", []):
        mock_translation.create_lemma_if_not_exists(mock_wiktionary_processor, mock_definitions, Entry('test', 'ana', ['def'], 'en'))
        assert len(mock_translation.check_if_page_exists.mock_calls) == 1
        mock_translation.check_if_page_exists.assert_called_with(mock_definitions.lemma)


def test_create_lemma_if_not_exists_lemma_does_not_exist(mock_translation, mock_wiktionary_processor, mock_definitions,
                                                         mocker):
    mock_translation.check_if_page_exists = MagicMock(return_value=False)
    mocker.patch("api.translation_v2.core.already_visited", [])
    mocker.patch("api.translation_v2.core.Page")
    mocker.patch("api.translation_v2.core.Site")
    mock_translation.process_wiktionary_wiki_page = MagicMock()

    mock_translation.create_lemma_if_not_exists(mock_wiktionary_processor, mock_definitions, Entry('test', 'ana', ['def'], 'en'))

    mock_translation.process_wiktionary_wiki_page.assert_called_once()
    mock_translation.check_if_page_exists.assert_called_with(mock_definitions.lemma)


def test_create_lemma_if_not_exists_already_visited(mock_translation, mock_wiktionary_processor, mock_definitions,
                                                    mocker):
    mocker.patch("api.translation_v2.core.already_visited", [mock_definitions.lemma])
    mock_translation.check_if_page_exists = MagicMock()

    mock_translation.create_lemma_if_not_exists(mock_wiktionary_processor, mock_definitions, Entry('test', 'ana', ['def'], 'en'))

    assert mock_translation.check_if_page_exists.call_count == 0


def test_create_lemma_if_not_exists_missing_part_of_speech(mock_translation, mock_wiktionary_processor,
                                                           mock_definitions, mocker):
    mocker.patch("api.translation_v2.core.already_visited", [])
    mock_translation.check_if_page_exists = MagicMock(return_value=False)
    mock_definitions.part_of_speech = None
    mocker.patch("api.translation_v2.core.Page")
    mocker.patch("api.translation_v2.core.Site")
    mock_translation.process_wiktionary_wiki_page = MagicMock()

    mock_translation.create_lemma_if_not_exists(mock_wiktionary_processor, mock_definitions, Entry('test', 'ana', ['def'], 'en'))

    mock_translation.check_if_page_exists.assert_called_once_with(mock_definitions.lemma)
    mock_translation.process_wiktionary_wiki_page.assert_called_once()


def test_create_lemma_if_not_exists_wiktionary_exception(mock_translation, mock_wiktionary_processor, mock_definitions,
                                                         mocker):
    mocker.patch("api.translation_v2.core.already_visited", [])
    mock_translation.check_if_page_exists = MagicMock(side_effect=WiktionaryProcessorException("Error"))
    mock_definitions.part_of_speech = "noun"

    with pytest.raises(WiktionaryProcessorException):
        mock_translation.create_lemma_if_not_exists(mock_wiktionary_processor, mock_definitions, Entry('test', 'ana', ['def'], 'en'))
