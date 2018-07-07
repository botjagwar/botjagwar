import json

from aiohttp.web import Response

from database.dictionary import Word


async def get_translation(request) -> Response:
    session = request.app['session_instance']
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


async def get_all_translations(request) -> Response:
    """
    Find all translations for the given word in the given language
    :return:
    """
    session = request.app['session_instance']
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

