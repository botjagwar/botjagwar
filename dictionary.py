from aiohttp import web
from aiohttp.web import Response

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_STORAGE_INFO_FILE = 'data/storage_info'
with open(DATABASE_STORAGE_INFO_FILE) as storage_file:
    STORAGE = storage_file.read()
ENGINE = create_engine('sqlite:///%s' % STORAGE)
Base = declarative_base()
routes = web.RouteTableDef()


class Dictionary(Base):
    __tablename__ = 'dictionary'
    id = Column(Integer, primary_key=True)
    word = Column(String(150))
    language = Column(String(6))
    definition = Column(String(250))
    definition_language = Column(String(6))
    part_of_speech = Column(String(15))

    def __init__(self):
        pass


class GeneratedDictionary(Base):
    __tablename__ = 'generated_dictionary'
    id = Column(Integer, primary_key=True)
    word = Column(String(150))
    language = Column(String(6))
    definition = Column(String(250))
    definition_language = Column(String(6))
    part_of_speech = Column(String(15))
    verified = Column(Boolean, default=False)


class DatabaseServiceHandler(object):
    def __init__(self):
        Base.metadata.create_all(ENGINE)
        self.db_session = sessionmaker(bind=ENGINE)

    def __del__(self):
        self.db_session.close_all()


database = DatabaseServiceHandler()


@routes.get('/definition/{language}/{word}')
async def get_definition(request):
    return Response(text='get definition')

@routes.post('/definition/{language}/{word}/edit')
async def edit_definition(request):
    return Response(text='post definition')

@routes.post('/definition/{language}/{word}/append')
async def edit_definition(request):
    return Response(text='append new definition')

@routes.delete('/definition/{language}/{word}/delete')
async def delete_definition(request):
    return Response(text='delete matching definition')


if __name__ == '__main__':
    app = web.Application()
    app.router.add_routes(routes)
    web.run_app(app, port=8001)
