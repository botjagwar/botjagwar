from api.entryprocessor.wiki.zh import ZHWiktionaryProcessor


def test_process_language_header_at_end_of_content():
    """Match language headers without a trailing newline."""
    processor = ZHWiktionaryProcessor(test=True)
    processor.set_title("狗")
    processor.set_text("==漢語==\n===名詞===\n# 一種[[動物]]。")

    entries = processor.get_all_entries()

    assert len(entries) == 1
    assert entries[0].part_of_speech == "ana"
    assert entries[0].language == "漢語"
    assert entries[0].definitions == ["一種動物。"]


def test_process_language_header_with_trailing_newline():
    """Match language headers followed by a trailing newline."""
    processor = ZHWiktionaryProcessor(test=True)
    processor.set_title("狗")
    processor.set_text("==漢語==\n===名詞===\n# 一種[[動物]]。\n")

    entries = processor.get_all_entries()

    assert len(entries) == 1
    assert entries[0].part_of_speech == "ana"
    assert entries[0].definitions == ["一種動物。"]
