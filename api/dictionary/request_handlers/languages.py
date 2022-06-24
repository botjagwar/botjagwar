import json

from aiohttp.web import Response, json_response

from api.dictionary.exceptions.http import InvalidDataError, ElementDoesNotExist
from api.dictionary.model import Language
from .routines import save_changes_on_disk


def language_exists(language_code, session):
    languages = [
        m.serialise() for m in session.query(Language)
        .filter(Language.iso_code == language_code)
        .all()]
    if len(languages) > 0:
        return True

    return False


async def list_languages(request) -> Response:
    session = request.app['session_instance']
    languages = [m.serialise() for m in session.query(Language).all()]
    return json_response(languages)


async def add_language(request) -> Response:
    session = request.app['session_instance']
    data = await request.json()
    if isinstance(data, str):
        data = json.loads(data)
    iso_code = request.match_info['iso_code']
    if language_exists(iso_code, session):
        return Response(status=460, text='Language already exists')
    # todo: use json_schema
    if 'iso_code' not in data or 'malagasy_name' not in data or 'english_name' not in data:
        raise InvalidDataError()
    # /todo
    language = Language(
        iso_code=iso_code,
        english_name=data['english_name'],
        malagasy_name=data['malagasy_name'],
        language_ancestor=data.get('language_ancestor', None),
    )
    session.add(language)
    await save_changes_on_disk(request.app, session)

    return Response(status=200)


async def get_language(request) -> Response:
    session = request.app['session_instance']
    code = request.match_info['iso_code']
    language_data = session.query(Language).filter(
        Language.iso_code == code).all()
    if len(language_data) < 1:
        raise ElementDoesNotExist()

    return json_response(language_data[0].serialise())


async def edit_language(request) -> Response:
    session = request.app['session_instance']
    data = await request.json()
    if isinstance(data, str):
        data = json.loads(data)
    language_data = session.query(Language).filter(
        Language.iso_code == data['iso_code']).all()
    if len(language_data) < 1:
        raise ElementDoesNotExist()
    else:
        language_data = language_data[0]

    language_data.iso_code = data['iso_code']
    language_data.english_name = data['english_name']
    language_data.malagasy_name = data['malagasy_name']
    language_data.language_ancestor = data.get('language_ancestor', None)

    await save_changes_on_disk(request.app, session)

    return Response(status=200)


async def delete_language(request) -> Response:
    session = request.app['session_instance']
    session.query(Language).filter(
        Language.iso_code == request.match_info['iso_code']).delete()

    await save_changes_on_disk(request.app, session)
    return Response(status=204)
