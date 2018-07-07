import json
import logging

from aiohttp.web import Response, json_response
from aiohttp.web import middleware

from database.dictionary import Word

log = logging.getLogger(__name__)

@middleware
async def json_error_handler(request, handler) -> Response:
    response = await handler(request)

    if 400 <= response.status < 600:
        data = {
            'type': 'error',
            'status': response.status,
            'error_message': response.text,
        }
        return json_response(data, status=response.status, headers=response.headers)
    return response


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