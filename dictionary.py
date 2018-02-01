from aiohttp import web
from aiohttp.web import Response

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, Definition, Word
import argparse

parser = argparse.ArgumentParser(description='Dictionary service')
parser.add_argument('--db-file', dest='STORAGE')
args = parser.parse_args()

if args.STORAGE:
    STORAGE = args.STORAGE
else:
    DATABASE_STORAGE_INFO_FILE = 'data/storage_info'
    with open(DATABASE_STORAGE_INFO_FILE) as storage_file:
        STORAGE = storage_file.read()

ENGINE = create_engine('sqlite:///%s' % STORAGE)
routes = web.RouteTableDef()
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
    if not jsons:
        status = 404
    else:
        status = 200
    return Response(text=json.dumps(jsons), status=status)


@routes.post('/entry/{language}/{word}/add')
async def add_entry(request):
    """
    Adds an antry to the dictionary.
    :param request:
    :return:
        HTTP 200 if entry is OK
    """
    data = await request.json()
    print(type(data))
    session = SessionClass()
    definition = Definition(
        definition=request.match_info['definition'],
        definition_language=request.match_info['definition_language'])
    word = Word(
        word=request.match_info['word'],
        language=request.match_info['language'],
        part_of_speech=request.match_info['part_of_speech'],
        definitions=[definition])
    session.add(definition)
    session.add(word)
    session.commit()
    session.flush()

    forged_word = word.serialise()
    return Response(status=200, text=json.dumps(forged_word))


@routes.put('/entry/{language}/{word}/edit')
async def edit_entry(request):
    # TODO
    data = await request.json()
    session = SessionClass()
    # ... code ...
    session.commit()
    return Response(status=500)



@routes.put('/entry/{language}/{word}/append')
async def append_definition(request):
    # TODO
    data = await request.json()
    session = SessionClass()
    # ... code ...
    session.commit()
    return Response(text='totoo')


@routes.delete('/entry/{language}/{word}/delete')
async def delete_entry(request):
    # TODO
    return Response(text='delete matching definition')

@routes.delete('/entry/{language}/{word}/delete')
async def delete_definition(request):
    # TODO
    return Response(text='delete matching definition')


if __name__ == '__main__':
    app = web.Application()
    app.router.add_routes(routes)
    web.run_app(app, port=8001)
