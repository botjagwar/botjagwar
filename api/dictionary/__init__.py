import json
import logging

from aiohttp.web import Response

from database.dictionary import Word

log = logging.getLogger(__name__)


async def get_dictionary(request) -> Response:
    session = request.app['session_instance']

    definitions = [w.serialise() for w in session.query(Word).filter(
        Word.language == request.match_info['language']).all()]
    if definitions:
        return Response(
            text=json.dumps(definitions),
            status=200)
    else:
        return Response(status=404, content_type='application/json')