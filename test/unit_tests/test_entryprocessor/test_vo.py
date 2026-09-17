from api.entryprocessor.wiki.vo import VOWiktionaryProcessor


def test_get_all_entries_parses_raw_vpvod_template() -> None:
    """Volapük extraction must work when callers provide text without a Page."""

    processor = VOWiktionaryProcessor()
    processor.set_title("hip")
    processor.set_text(
        """{{VpVöd
|vöd=hip
|klad=subsat
|WW=Hüfte.
}}"""
    )

    entries = processor.get_all_entries()

    assert len(entries) == 1
    assert entries[0].entry == "hip"
    assert entries[0].language == "vo"
    assert entries[0].part_of_speech == "ana"
    assert entries[0].definitions == ["Hüfte."]
