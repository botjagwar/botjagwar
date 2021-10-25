import asyncio
import json
import logging

from aiohttp.web import Response
from aiohttp.web_exceptions import HTTPNoContent, HTTPOk

from database.dictionary import Definition, Word
from database.exceptions.http import WordAlreadyExistsException, WordDoesNotExistException, InvalidJsonReceivedException
from .routines import save_changes_on_disk

log = logging.getLogger(__name__)


def get_word(session, word, language, part_of_speech):
    word = session.query(Word).filter_by(
        word=word,
        language=language,
        part_of_speech=part_of_speech).all()
    return word[0]


def create_definition_if_not_exists(
        session,
        definition: str,
        definition_language: str) -> Definition:
    definitions = session.query(Definition).filter_by(
        definition=definition,
        definition_language=definition_language
    ).all()
    if not definitions:
        definition = Definition(
            definition=definition,
            language=definition_language
        )
        session.add(definition)
    else:
        definition = definitions[0]
    return definition


def word_with_definition_exists(
        session,
        word_,
        language,
        part_of_speech,
        definition):
    words = session.query(Word).filter_by(
        word=word_,
        language=language,
        part_of_speech=part_of_speech).all()
    if not words:
        return False
    else:
        for word in words:
            for found_definition in word.definitions:
                if found_definition.definition == definition:
                    return True
        return False


def word_exists(session, word, language, part_of_speech):
    word = session.query(Word).filter_by(
        word=word,
        language=language,
        part_of_speech=part_of_speech).all()
    if not word:
        return False
    else:
        return True


async def get_word_by_id(request) -> Response:
    session = request.app['session_instance']

    objekt = session.query(Word).filter_by(
        id=request.match_info['word_id']).one()

    return Response(
        text=json.dumps(objekt.serialise()),
        status=HTTPOk.status_code,
        content_type='application/json')


async def get_entry(request) -> Response:
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
        raise WordDoesNotExistException()
    else:
        return Response(
            text=json.dumps(jsons),
            status=HTTPOk.status_code,
            content_type='application/json')


def _add_entry(data, session):
    normalised_retained_definitions = []
    if 'definitions' in data and len(data['definitions']) > 0:
        for definition in data['definitions']:
            definition_object = create_definition_if_not_exists(
                session, definition['definition'], definition['definition_language'])
            normalised_retained_definitions.append(definition_object)
    else:
        raise InvalidJsonReceivedException()

    if word_exists(
            session,
            data['word'],
            data['language'],
            data['part_of_speech']):
        # Get the word and mix it with the normalised retained definitions
        word = get_word(
            session,
            data['word'],
            data['language'],
            data['part_of_speech'])
        normalised_retained_definitions += word.definitions
        normalised_retained_definitions = list(
            set(normalised_retained_definitions))
        if word.definitions == normalised_retained_definitions:
            raise WordAlreadyExistsException()
        else:
            word.definitions = normalised_retained_definitions

        return word
    else:
        # Add a new word if not.
        word = Word(
            word=data['word'],
            language=data['language'],
            part_of_speech=data['part_of_speech'],
            definitions=normalised_retained_definitions)
        # Updating database

        session.add(word)

    return word


async def add_batch(request) -> Response:
    """
    Adds a batch of entries to the dictionary.
    If the entry exists but not with the definition, the definition will automatically
    appended. If the definition also exists, HTTP 460 will be raised.
    :param request:
    :return:
        HTTP 200 if entry is OK
        HTTP 460 if entry already exists
    """
    ret_payload = []
    datas = await request.json()
    session = request.app['session_instance']
    errors = 0

    for data in datas:
        if isinstance(data, str):
            data = json.loads(data)

        word = _add_entry(data, session)
        # Search if definition already exists.

    session.commit()
    session.flush()

    return Response(
        status=HTTPOk.status_code,
        text=json.dumps(ret_payload),
        content_type='application/json')


async def add_entry(request) -> Response:
    """
    Adds an entry to the dictionary.
    If the entry exists but not with the definition, the definition will automatically
    appended. If the definition also exists, HTTP 460 will be raised.
    :param request:
    :return:
        HTTP 200 if entry is OK
        HTTP 460 if entry already exists
    """
    data = await request.json()

    if isinstance(data, str):
        data = json.loads(data)

    session = request.app['session_instance']
    if isinstance(data, str):
        data = json.loads(data)

    data['language'] = request.match_info['language']
    word = _add_entry(data, session)
    forged_word = word.serialise()
    asyncio.ensure_future(save_changes_on_disk(request.app, session))

    # Return HTTP response
    return Response(
        status=HTTPOk.status_code,
        text=json.dumps(forged_word),
        content_type='application/json')


async def edit_entry(request) -> Response:
    """
    Updates the current entry by the one given in JSON.
    The engine will try to find if the entry and definitions
    already exist.
    :param request:
    :return:
        HTTP 200 with the new entry JSON
    """
    session = request.app['session_instance']

    with session.no_autoflush:
        # Search if word already exists.
        word = session.query(Word).filter_by(
            id=request.match_info['word_id']).all()
        # return exception if it doesn't
        # that because we'd not be editing otherwise.
        if not word:
            raise WordDoesNotExistException()

        word = word[0]
        definitions = []
        data = await request.json()
        assert isinstance(data, dict)
        for definition_json in data['definitions']:
            definition = create_definition_if_not_exists(
                session,
                definition_json['definition'],
                definition_json['definition_language']
            )
            definitions.append(definition)

        word.part_of_speech = data['part_of_speech']
        word.definitions = definitions

    asyncio.ensure_future(save_changes_on_disk(request.app, session))
    return Response(
        status=HTTPOk.status_code,
        text=json.dumps(
            word.serialise()),
        content_type='application/json')


async def delete_entry(request) -> Response:
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

    asyncio.ensure_future(save_changes_on_disk(request.app, session))
    return Response(
        status=HTTPNoContent.status_code,
        content_type='application/json')
