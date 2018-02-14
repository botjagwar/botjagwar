from aiohttp.web import Response

import database.http as db_http
from database import Definition, Word
import json

from .routines import save_changes_on_disk

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


def word_exists(session, word, language, part_of_speech):
    word = session.query(Word).filter_by(
        word=word,
        language=language,
        part_of_speech=part_of_speech).all()
    if not word:
        return False
    else:
        return True


async def get_entry(request):
    """
    Return a list of entries matching the word and the language.
    :param request:
    :return:
        HTTP 200 if the word exists
        HTTP 404 otherwise
    """
    session = request.app['session_instance']
    objects = session.query(Word).filter_by(
        word=request.match_info['word'],
        language=request.match_info['language']).all()
    jsons = [objekt.serialise() for objekt in objects]
    if not jsons:
        raise db_http.WordDoesNotExistException()
    else:
        return Response(text=json.dumps(jsons), status=200, content_type='application/json')


async def add_entry(request):
    """
    Adds an antry to the dictionary.
    :param request:
    :return:
        HTTP 200 if entry is OK
    """
    data = await request.json()
    session = request.app['session_instance']

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
    await save_changes_on_disk(request.app, session)

    # Return HTTP response
    forged_word = word.serialise()
    return Response(status=200, text=json.dumps(forged_word), content_type='application/json')


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


    session = request.app['session_instance']

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

    await save_changes_on_disk(request.app, session)
    return Response(status=200, text=json.dumps(word.serialise()), content_type='application/json')


async def delete_entry(request):
    """
    Delete the entry from the database. The definitions however
    are kept. They are also deleted if 'delete_dependent definitions'
    is set.
    :param request:
    :return:
    """
    # Search if word already exists.
    session = request.app['session_instance']

    session.query(Word).filter(
        Word.id == request.match_info['word_id']).delete()

    await save_changes_on_disk(request.app, session)
    return Response(status=204, content_type='application/json')