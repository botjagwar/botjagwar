from models import TypeCheckedObject
from modules.database import Database

class Word(TypeCheckedObject):
    _additional = False
    properties_types = dict(
        entry=unicode,
        part_of_speech=str,
        language=str)


class Entry(TypeCheckedObject):
    _additional = False
    properties_types = dict(
        entry=unicode,
        part_of_speech=str,
        entry_definition=unicode,
        language=str,
        origin_wiktionary_edition=unicode,
        origin_wiktionary_page_name=unicode)

    def add_to_database(self):
        pass


class Translation(TypeCheckedObject):
    _additional = False
    properties_types = dict(
        origin=Word,
        target=Word)


__all__ = ['Entry', 'Translation']