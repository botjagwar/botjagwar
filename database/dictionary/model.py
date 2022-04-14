
from sqlalchemy import Integer, String, DateTime, TEXT
from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.databasemanager import DictionaryDatabaseManager
from database.dictionary.json import Definition as DefinitionSerialiser
from database.dictionary.json import Word as WordSerialiser
from .controller import Definition as DefinitionController
from .controller import Word as WordController

Base = declarative_base()
dictionary_association = Table(
    'dictionary', Base.metadata,
    Column('word', Integer, ForeignKey('word.id')),
    Column('definition', Integer, ForeignKey('definitions.id'))
)


class Definition(Base):
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
        self.definition = definition
        self.definition_language = language

    def from_json(self, json_data):
        pass

    def serialise(self):
        return self.Serialiser(self).serialise()

    def serialise_with_words(self):
        return self.Serialiser(self).serialise_with_words()

    def serialise_xml(self):
        return self.Serialiser(self).serialise_xml()

    def get_schema(self):
        """
        Returns a serialised object containing the current object's schema.
        Useful to generate forms.
        :return:
        """
        pass


class Word(Base):
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

    def from_json(self, json_data):
        pass

    def serialise(self):
        return self.Serialiser(self).serialise()

    def serialise_xml(self):
        return self.Serialiser(self).serialise_xml()

    def serialise_without_definition(self):
        return self.Serialiser(self).serialise_without_definition()

    def serialise_to_entry(self):
        return self.Serialiser(self).serialise_to_entry()

    def set_definition(self, definitions: list):
        return self.Controller(self).set_definition(definitions)

    def add_definition(self, definition: Definition):
        return self.Controller(self).add_definition(definition)

    def remove_definition(self, definition: Definition):
        return self.Controller(self).remove_definition(definition)

    @property
    def schema(self):
        """
        Returns a serialised object containing the current object's schema.
        Useful to generate forms.
        :return:
        """
        return {}
