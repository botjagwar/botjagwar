from aiohttp import web
from aiohttp.web import Response
import argparse

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, Definition, Word
import database.http as db_http

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


def word_exists(session, word, language, part_of_speech):
    word = session.query(Word).filter_by(
        word=word,
        language=language,
        part_of_speech=part_of_speech).all()
    if not word:
        return False
    else:
        return True


def create_definition_if_not_exists(session, definition, definition_language):
    definitions = session.query(Definition).filter_by(
        definition=definition,
        definition_language=definition_language
    ).all()
    if not definitions:
        definition = Definition(
            definition=definition,
            definition_language=definition_language
        )
        session.add(definition)
    else:
        definition = definitions[0]
    return definition

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
        raise db_http.WordDoesNotExistException()
    else:
        return Response(text=json.dumps(jsons), status=200)


@routes.post('/entry/{language}/add')
async def add_entry(request):
    """
    Adds an antry to the dictionary.
    :param request:
    :return:
        HTTP 200 if entry is OK
    """
    jsondata = await request.json()
    data = json.loads(jsondata)
    session = SessionClass()

    # Search if definition already exists.
    retained_definitions = []
    if 'definitions' in data and len(data['definitions']) > 0:
        for definition in data['definitions']:
            definition_object = create_definition_if_not_exists(
                session, definition['definition'], definition['definition_language'])

            retained_definitions.append(definition_object)
    else:
        raise db_http.InvalidJsonReceivedException()

    # Search if word already exists.
    word = session.query(Word).filter_by(
        word=data['word'],
        language=request.match_info['language'],
        part_of_speech=data['part_of_speech']).all()
    # return HTTP_WORD_ALREADY_EXISTS if it does
    # that because we'd not be adding otherwise.
    if word_exists(
            session, data['word'],
            request.match_info['language'],
            data['part_of_speech']):
        raise db_http.WordAlreadyExistsException()

    # Add a new word if not.
    word = Word(
        word=data['word'],
        language=request.match_info['language'],
        part_of_speech=data['part_of_speech'],
        definitions=retained_definitions)

    # Updating database
    session.add(word)
    session.commit()
    session.flush()

    # Return HTTP response
    forged_word = word.serialise()
    return Response(status=200, text=json.dumps(forged_word))


@routes.put('/entry/{word_id}/edit')
async def edit_entry(request):
    """
    Updates the current entry by the one given in JSON.
    The engine will try to find if the entry and definitions
    already exist.
    :param request:
    :return:
        HTTP 200 with the new entry JSON
    """
    jsondata = await request.json()
    data = json.loads(jsondata)

    session = SessionClass()

    # Search if word already exists.
    word = session.query(Word).filter_by(
        id=request.match_info['word_id']).all()
    # return exception if it doesn't
    # that because we'd not be editing otherwise.
    if not word:
        raise db_http.WordDoesNotExistException()

    word = word[0]
    definitions = []
    for definition_json in data['definitions']:
        definition = create_definition_if_not_exists(
            session,
            definition_json['definition'],
            definition_json['definition_language']
        )
        definitions.append(definition)

    word.definitions = definitions
    word.part_of_speech = data['part_of_speech']

    session.commit()
    session.flush()
    return Response(status=200, text=json.dumps(word.serialise()))


@routes.put('/entry/{language}/{word}/append')
async def append_definition(request):
    """
    Adds a new definition to the entry.
    :param request:
    :return:
        HTTP 200 with the new entry JSON.
    """
    data = await request.json()
    session = SessionClass()
    # ... code ...
    session.commit()
    session.flush()

    return Response(text='totoo', status=501)


@routes.delete('/entry/{language}/{word}/delete')
async def delete_entry(request):
    """
    Delete the entry from the database. The definitions however
    are kept. They are also deleted if 'delete_dependent definitions'
    is set.
    :param request:
    :return:
    """
    # TODO
    return Response(text='delete matching definition', status=501)


@routes.delete('/entry/{language}/{word}/delete')
async def delete_definition(request):
    """
    Delete the definition.
    :param request:
    :return:
        HTTP 204 if the definition has been successfully deleted
        HTTP 404 if definition is not foud
    """
    # TODO
    return Response(text='delete matching definition', status=501)


if __name__ == '__main__':
    app = web.Application()
    app.router.add_routes(routes)
    web.run_app(app, port=8001)
