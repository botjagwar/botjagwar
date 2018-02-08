
from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy import Integer, String

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()
dictionary_association = Table('dictionary', Base.metadata,
    Column('word', Integer, ForeignKey('word.id')),
    Column('definition', Integer, ForeignKey('definitions.id'))
)


class Word(Base):
    __tablename__ = 'word'
    id = Column(Integer, primary_key=True)
    word = Column(String(150))
    language = Column(String(6))
    part_of_speech = Column(String(15))
    definitions = relationship(
        "Definition",
        secondary=dictionary_association,
        back_populates="words")

    def serialise(self):
        word_data = {
            'type': self.__class__.__name__,
            'id': self.id,
            'word': self.word,
            'language': self.language,
            'part_of_speech': self.part_of_speech,
            'definitions': [definition.serialise() for definition in self.definitions],
        }
        return word_data

    def serialise_without_definition(self):
        word_data = {
            'type': self.__class__.__name__,
            'id': self.id,
            'word': self.word,
            'language': self.language,
            'part_of_speech': self.part_of_speech,
        }
        return word_data

    def set_definition(self, definitions):
        """
        Replace the existing definition set by the one given in argument
        :param definition:
        :return:
        """
        assert isinstance(definitions, list)
        self.definitions = definitions

    def add_definition(self, definition):
        if definition not in self.definitions:
            self.definitions.append(definition)

    def remove_definition(self, definition):
        if definition not in self.definitions:
            self.definitions.remove(definition)


class Definition(Base):
    __tablename__ = 'definitions'
    id = Column(Integer, primary_key=True)
    definition = Column(String(250))
    definition_language = Column(String(6))
    words = relationship(
        'Word',
        secondary=dictionary_association,
        back_populates='definitions')

    def serialise(self):
        definition_data = {
            'type': self.__class__.__name__,
            'id': self.id,
            'definition': self.definition,
            'language': self.definition_language
        }
        return definition_data

    def serialise_with_words(self):
        definition_data = {
            'type': self.__class__.__name__,
            'id': self.id,
            'definition': self.definition,
            'language': self.definition_language,
            'words': [w.serialise_without_definition() for w in self.words]
        }
        return definition_data