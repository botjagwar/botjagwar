from aiohttp import web
from aiohttp.web import Response

import json

from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy import Integer, String

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_STORAGE_INFO_FILE = 'data/storage_info'
with open(DATABASE_STORAGE_INFO_FILE) as storage_file:
    STORAGE = storage_file.read()
ENGINE = create_engine('sqlite:///%s' % STORAGE)
Base = declarative_base()
routes = web.RouteTableDef()


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
            'word': self.word,
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


Base.metadata.create_all(ENGINE)
SessionClass = sessionmaker(bind=ENGINE)


@routes.get('/entry/{language}/{word}')
async def get_entry(request):
    """
    Return a list of entries matching the word and the language.
    :param request:
    :return:
        HTTP 200 if the word exists
        HTTP 404 otherwise
    """
    session = SessionClass()
    objects = session.query(Word).filter_by(
        word=request.match_info['word'],
        language=request.match_info['language']).all()
    jsons = [objekt.serialise() for objekt in objects]
    return Response(text=json.dumps(jsons), status=200)


@routes.get('/entry/{language}/{word}/add')
async def add_entry(request):
    """
    Adds an antry to the dictionary.
    :param request:
    :return:
        HTTP 200 if entry is OK
    """
    # FIXME
    session = SessionClass()
    definition = Definition(definition='sdflksf', definition_language='el')
    word = Word(word=request.match_info['word'],
                language=request.match_info['language'],
                part_of_speech='ana',
                definitions=[definition])
    session.add(definition)
    session.add(word)
    session.commit()
    return Response(status=200, text='OK BOSS')


@routes.post('/entry/{language}/{word}/edit')
async def edit_entry(request):
    data = await request.json()
    session = SessionClass()
    # ... code ...
    session.commit()



@routes.post('/entry/{language}/{word}/append')
async def edit_definition(request):
    data = await request.json()
    session = SessionClass()
    # ... code ...
    session.commit()


@routes.delete('/entry/{language}/{word}/delete')
async def delete_definition(request):
    return Response(text='delete matching definition')


if __name__ == '__main__':
    app = web.Application()
    app.router.add_routes(routes)
    web.run_app(app, port=8001)
