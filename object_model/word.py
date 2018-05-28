from object_model import TypeCheckedObject

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

    def to_tuple(self):
        return self.word, self.part_of_speech, self.language, self.entry_definition

    def __lt__(self, other):
        """
        Used for sorting entries. Language code will be considered
        :param other:
        :return:
        """
        return self.language < other.language

    def __repr__(self):
        return "Entry{entry=%s, language=%s, part_of_speech=%s, entry_definition=%s}" % (
            self.entry, self.language, self.part_of_speech, self.entry_definition)

class Translation(TypeCheckedObject):
    _additional = False
    properties_types = dict(
        origin=Word,
        target=Word)


__all__ = ['Entry', 'Translation']