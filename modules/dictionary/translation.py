from aiohttp.web import Response

from database import Word
import json


async def get_translation(request):
    session_class = request.app['database_session']
    session = session_class()
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


async def get_all_translations(request):
    """
    Find all translations for the given word in the given language
    :return:
    """
    session_class = request.app['database_session']
    session = session_class()
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

