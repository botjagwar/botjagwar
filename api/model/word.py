from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional, List, Dict

from api.serialisers.word import (
    Entry as EntrySerialiser,
    Translation as TranslationSerialiser,
)


@dataclass
class Word(object):
    entry: str
    part_of_speech: str
    language: str


@dataclass
class Entry(object):
    """
    Non-DB model for entries
    """

    entry: str
    part_of_speech: str
    definitions: List[str]
    language: str
    additional_data: Optional[Dict] = field(default_factory=dict)

    @classmethod
    def from_word(cls, model):
        return cls(
            entry=model.word,
            part_of_speech=model.part_of_speech,
            language=model.language,
            definitions=deepcopy(model.definitions),
            additional_data=deepcopy(model.additional_data),
        )

    def to_tuple(self):
        return self.entry, self.part_of_speech, self.language, self.definitions

    def serialise(self) -> dict:
        return EntrySerialiser(self).serialise()

    def __lt__(self, other):
        """
        Used for sorting entries. Language code will be considered
        :param other:
        :return:
        """
        return self.__cmp__(other) < 0

    def __cmp__(self, other):
        """
        Comparison, in the following order: language > entry > part_of_speech
        :param other:
        :return:
        """
        if hasattr(self, "language") and hasattr(other, "language"):
            if self.language == other.language:
                if hasattr(self, "entry") and hasattr(other, "entry"):
                    if self.entry == other.entry:  # noqa
                        if hasattr(self, "part_of_speech") and hasattr(
                            other, "part_of_speech"
                        ):
                            if self.part_of_speech == other.part_of_speech:
                                return 0
                            if self.part_of_speech < other.part_of_speech:
                                return -1
                            return 1
                        return 0
                    if self.entry < other.entry:
                        return -1
                    return 1
                return 0
            if self.language < other.language:
                return -1
            return 1
        return 1

    def overlay(self, other):
        self.language = other.language
        self.part_of_speech = other.part_of_speech
        self.definitions = other.definitions
        for apt, ap_type in other.properties_types.items():
            print(other)
            if hasattr(other, apt):
                setattr(self, apt, deepcopy(getattr(other, apt)))

        return deepcopy(self)


@dataclass(order=True)
class Translation(object):
    word: str
    language: str
    part_of_speech: str
    definition: str

    def serialise(self) -> dict:
        return TranslationSerialiser(self).serialise()


__all__ = ["Word", "Entry", "Translation"]
