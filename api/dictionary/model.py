from typing import Optional

from sqlalchemy import Integer, String, DateTime, TEXT
from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.dictionary.controller import Definition as DefinitionController
from api.dictionary.controller import Word as WordController
from api.dictionary.serialisers.json import Definition as DefinitionSerialiser
from api.dictionary.serialisers.json import JSONBuilder
from api.dictionary.serialisers.json import Word as WordSerialiser

Base = declarative_base()
dictionary_association = Table(
    'dictionary', Base.metadata,
    Column('word', Integer, ForeignKey('word.id')),
    Column('definition', Integer, ForeignKey('definitions.id'))
)


class Serialisable(object):
    Serialiser: JSONBuilder = None
    Controller: Optional = None

    def serialise(self):
        """
        Pass-through to designated serialiser
        :return:
        """
        if self.Serialiser is not None:
            return self.Serialiser(self).serialise()
        else:
            raise NotImplementedError(f'No serialiser is defined for {self.__class__.__name__} class')


class Definition(Base, Serialisable):
    """
    Database model for definition
    """
    Serialiser = DefinitionSerialiser
    Controller = DefinitionController

    __tablename__ = 'definitions'
    id = Column(Integer, primary_key=True)
    date_changed = Column(DateTime, default=func.now())
    definition = Column(TEXT)
    definition_language = Column(String(6))
    words = relationship(
        'Word',
        secondary=dictionary_association,
        back_populates='definitions')

    def __init__(self, definition: str, language: str):
        super(Definition, self).__init__()
        self.definition = definition
        self.definition_language = language

    def from_json(self, json_data):
        pass

    def serialise_with_words(self):
        return self.Serialiser(self).serialise_with_words()


class Word(Base, Serialisable):
    """
    Database model for Word
    """
    Serialiser = WordSerialiser
    Controller = WordController

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

    def __init__(
            self,
            word: str,
            language: str,
            part_of_speech: str,
            definitions: list):
        self.word = word
        self.language = language
        self.part_of_speech = part_of_speech

        for definition in definitions:
            if not isinstance(definition, Definition):
                raise TypeError(
                    "Every definition inside definitions list must be a Definition object")

        self.definitions = definitions

    @property
    def additional_data(self):
        from api.databasemanager import DictionaryDatabaseManager
        dbm = DictionaryDatabaseManager()
        if self.id:
            sql = f"select word_id, type, information from additional_word_information where word_id = {self.id}"
            rq = dbm.session.execute(sql)
            ret = {}
            for w_id, adt, info in rq.fetchall():
                if adt in ret:
                    ret[adt].append(info)
                else:
                    ret[adt] = [info]
            return ret
        else:
            return None


class Language(Base, Serialisable):
    __tablename__ = 'language'
    iso_code = Column(String(6), primary_key=True)
    english_name = Column(String(100))
    malagasy_name = Column(String(100))
    language_ancestor = Column(String(6))

    def __init__(self, iso_code, english_name, malagasy_name, language_ancestor):
        self.iso_code = iso_code
        self.english_name = english_name
        self.malagasy_name = malagasy_name
        self.language_ancestor = language_ancestor

    def get_schema(self):
        pass


