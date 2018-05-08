from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy import Integer, String, DateTime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()
dictionary_association = Table('dictionary', Base.metadata,
    Column('word', Integer, ForeignKey('word.id')),
    Column('definition', Integer, ForeignKey('definitions.id'))
)


class Definition(Base):
    __tablename__ = 'definitions'
    id = Column(Integer, primary_key=True)
    date_changed = Column(DateTime, default=func.now())
    definition = Column(String(250))
    definition_language = Column(String(6))
    words = relationship(
        'Word',
        secondary=dictionary_association,
        back_populates='definitions')

    def __init__(self, definition: str, language: str):
        self.definition = definition
        self.definition_language = language

    def serialise(self):
        definition_data = {
            'type': self.__class__.__name__,
            'id': self.id,
            'definition': self.definition,
            'language': self.definition_language,
            'last_modified':
                self.date_changed.strftime("%Y-%m-%d %H:%M:%S")
                if self.date_changed is not None else ''
        }
        return definition_data

    def from_json(self, json_data):
        pass

    def serialise_with_words(self):
        definition_data = self.serialise()
        definition_data['words'] = [w.serialise_without_definition() for w in self.words],
        return definition_data

    def get_schema(self):
        """
        Returns a serialised object containing the current object's schema.
        Useful to generate forms.
        :return:
        """
        pass


class Word(Base):
    __tablename__ = 'word'
    id = Column(Integer, primary_key=True)
    date_changed = Column(DateTime, default=func.now())
    word = Column(String(150))
    language = Column(String(6))
    part_of_speech = Column(String(15))
    definitions = relationship(
        "Definition",
        secondary=dictionary_association,
        back_populates="words")

    def __init__(self, word: str, language: str, part_of_speech: str, definitions: list):
        self.word = word
        self.language = language
        self.part_of_speech = part_of_speech

        for definition in definitions:
            if not isinstance(definition, Definition):
                raise TypeError("Every definition inside definitions list must be a Definition object")

        self.definitions = definitions

    def from_json(self, json_data):
        pass

    def serialise(self):
        word_data = self.serialise_without_definition()
        word_data['definitions'] = [definition.serialise() for definition in self.definitions]
        return word_data

    def serialise_without_definition(self):
        word_data = {
            'type': self.__class__.__name__,
            'id': self.id,
            'word': self.word,
            'language': self.language,
            'part_of_speech': self.part_of_speech,
            'last_modified':
                self.date_changed.strftime("%Y-%m-%d %H:%M:%S")
                if self.date_changed is not None else ''
        }
        return word_data

    def set_definition(self, definitions: list):
        """
        Replace the existing definition set by the one given in argument
        :param definition:
        :return:
        """
        for d in definitions:
            if not isinstance(d, Definition):
                raise TypeError("A Definition object is expected.")

        self.definitions = definitions

    def add_definition(self, definition: Definition):
        if definition not in self.definitions:
            self.definitions.append(definition)

    def remove_definition(self, definition: Definition):
        if definition not in self.definitions:
            self.definitions.remove(definition)

    def get_schema(self):
        """
        Returns a serialised object containing the current object's schema.
        Useful to generate forms.
        :return:
        """
        pass
