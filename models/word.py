from models import TypeCheckedObject

class Word(TypeCheckedObject):
    _additional = False
    properties_types = dict(
        entry=str,
        part_of_speech=str,
        language=str)


class Entry(TypeCheckedObject):
    _additional = False
    properties_types = dict(
        entry=str,
        part_of_speech=str,
        entry_definition=list,
        language=str,
        origin_wiktionary_edition=str,
        origin_wiktionary_page_name=str)

    def add_to_database(self):
        pass


class Translation(TypeCheckedObject):
    _additional = False
    properties_types = dict(
        origin=Word,
        target=Word)


__all__ = ['Entry', 'Translation']