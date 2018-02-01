
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
            'id': self.id,
            'word': self.word,
            'language': self.language,
            'part_of_speech': self.part_of_speech,
            'definitions': [definition.serialise() for definition in self.definitions],
        }
        print (self.definitions)
        return word_data


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
            'definition': self.definition,
            'language': self.definition_language
        }
        return definition_data