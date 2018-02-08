from aiohttp import web
from aiohttp.web import Response
import argparse

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, Definition, Word
import database.http as db_http

parser = argparse.ArgumentParser(description='Dictionary service')
parser.add_argument('--db-file', dest='STORAGE', required=False)
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
SessionClass = sessionmaker(bind=ENGINE, autoflush=True)


def word_exists(session, word, language, part_of_speech):
    word = session.query(Word).filter_by(
        word=word,
        language=language,
        part_of_speech=part_of_speech).all()
    if not word:
        return False
    else:
        return True


def get_word(session, word, language, part_of_speech):
    word = session.query(Word).filter_by(
        word=word,
        language=language,
        part_of_speech=part_of_speech).all()
    return word[0]


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
        return Response(text=json.dumps(jsons), status=200, content_type='application/json')


@routes.post('/entry/{language}/create')
async def add_entry(request):
    """
    Adds an antry to the dictionary.
    :param request:
    :return:
        HTTP 200 if entry is OK
    """
    data = await request.json()
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
    return Response(status=200, text=json.dumps(forged_word), content_type='application/json')


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
    return Response(status=200, text=json.dumps(word.serialise()), content_type='application/json')


@routes.delete('/entry/{word_id}/delete')
async def delete_entry(request):
    """
    Delete the entry from the database. The definitions however
    are kept. They are also deleted if 'delete_dependent definitions'
    is set.
    :param request:
    :return:
    """
    # Search if word already exists.
    session = SessionClass()
    session.query(Word).filter(
        Word.id == request.match_info['word_id']).delete()

    session.commit()
    session.flush()
    return Response(status=204, content_type='application/json')


@routes.get('/definition/{definition_id}')
async def get_definition(request):
    session = SessionClass()
    definitions = [m.serialise() for m in session.query(Definition).filter(
        Definition.id == request.match_info['definition_id']).all()]
    if definitions:
        return Response(
            text=json.dumps(definitions),
            status=200)
    else:
        return Response(status=404, content_type='application/json')


@routes.get('/translations/{origin}/{target}/{word}')
async def get_translation(request):
    session = SessionClass()
    origin, target = request.match_info['origin'], request.match_info['target']

    words = [w.serialise() for w in session.query(Word)
        .filter(Word.language == origin)
        .filter(Word.word == request.match_info['word'])
        .all()]
    translations = []
    for word in words:
        definitions = word['definitions']
        for definition in definitions:
            if definition['language'] == target:
                translations.append(definition)

    return Response(
        text=json.dumps(translations), status=200, content_type='application/json')


@routes.get('/translations/{origin}/{word}')
async def get_translation(request):
    session = SessionClass()
    origin = request.match_info['origin']

    words = [w.serialise() for w in session.query(Word)
        .filter(Word.language == origin)
        .filter(Word.word == request.match_info['word'])
        .all()]
    translations = []
    for word in words:
        definitions = word['definitions']
        for definition in definitions:
            translations.append(definition)

    return Response(
        text=json.dumps(translations), status=200, content_type='application/json')


@routes.post('/definition/search')
async def search_definition(request):
    session = SessionClass()
    jsondata = await request.json()
    data = json.loads(jsondata)
    definitions = [m.serialise() for m in session.query(
        Definition).filter(Definition.definition.like(data['definition'])).all()]

    return Response(
        text=json.dumps(definitions), status=200, content_type='application/json')


@routes.delete('/definition/{definition_id}/delete')
async def delete_definition(request):
    """
    Delete the definition.
    :param request:
    :return:
        HTTP 204 if the definition has been successfully deleted
    """
    # Search if definition already exists.
    session = SessionClass()
    session.query(Definition).filter(
        Definition.id == request.match_info['definition_id']).delete()

    session.commit()
    session.flush()
    return Response(status=204)

if __name__ == '__main__':
    app = web.Application()
    app.router.add_routes(routes)
    web.run_app(app, port=8001)
