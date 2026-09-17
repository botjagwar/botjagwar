import csv

import pytest

from api.model.word import Entry
from api.storage import (
    CacheMissError,
    EntryPageFileReader,
    EntryPageFileWriter,
    MissingTranslationCsvWriter,
    MissingTranslationFileReader,
    MissingTranslationFileWriter,
    SiteExtractorCacheEngine,
)


@pytest.fixture
def user_data_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "user_data").mkdir()
    return tmp_path


def test_entry_page_file_writer_and_reader_round_trip(user_data_directory):
    entry = Entry("trano", "ana", ["house"], "mg")
    writer = EntryPageFileWriter("mg")

    writer.add(entry)
    writer.add(entry)
    writer.write()

    reader = EntryPageFileReader("mg")
    reader.read()

    assert reader.page_dump == {"trano": [entry]}


def test_entry_page_file_reader_handles_missing_dump(user_data_directory):
    reader = EntryPageFileReader("missing")

    reader.read()

    assert reader.page_dump == {}


def test_missing_translation_file_writer_and_reader_round_trip(user_data_directory):
    writer = MissingTranslationFileWriter("mg")

    writer.add("house")
    writer.add("house")
    writer.add("tree")
    writer.write()
    writer.mising_translations_file.close()

    reader = MissingTranslationFileReader("mg")
    reader.read()

    assert reader.mising_translations == {"house": 2, "tree": 1}


def test_missing_translation_csv_writer_excludes_known_words(user_data_directory, mocker):
    reader = mocker.Mock(mising_translations={"house": 2, "tree": 1})
    lookup = mocker.Mock()
    lookup.word_exists.side_effect = lambda word: word == "house"
    mocker.patch("api.storage.MissingTranslationFileReader", return_value=reader)
    mocker.patch("api.storage.FastTranslationLookup", return_value=lookup)

    writer = MissingTranslationCsvWriter("mg")
    output_path = user_data_directory / "missing-%s.csv"
    writer.to_csv(str(output_path))

    with (user_data_directory / "missing-mg.csv").open() as output_file:
        assert list(csv.DictReader(output_file)) == [{"word": "tree", "hits": "1"}]
    reader.read.assert_called_once()
    lookup.build_table.assert_called_once()


def test_site_extractor_cache_persists_and_reports_misses(user_data_directory):
    cache = SiteExtractorCacheEngine("wiktionary")
    cache.add("trano", "content")
    cache.write()

    restored = SiteExtractorCacheEngine("wiktionary")

    assert restored.get("trano") == "content"
    assert list(restored.iterate()) == ["content"]
    assert restored.list() == ["trano"]
    with pytest.raises(CacheMissError):
        restored.get("missing")
