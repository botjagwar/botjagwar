from models import BaseEntry


class Entry(BaseEntry):
    _additional = False
    properties_types = dict(
        entry=unicode,
        part_of_speech=str,
        entry_definition=unicode,
        language=str,
        origin_wiktionary_edition=unicode,
        origin_wiktionary_page_name=unicode,
    )


__all__ = ['Entry']