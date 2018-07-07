import json
import logging

from aiohttp.web import Response
from aiohttp.web import middleware

from database.dictionary import Word

log = logging.getLogger(__name__)


@middleware
async def json_error_handler(request, handler) -> Response:
    response = await handler(request)
    if 400 <= response.status < 600:
        log.info('HTTP Status %d / JSON Error handler middleware active' % response.status)
        data = {
            'type': 'error',
            'status': response.status,
            'error_message': response.text,
        }
        log.debug(data)
        response.text = json.loads(data)
    return response


@middleware
async def auto_committer(request, handler) -> Response:
    response = await handler(request)
    if 'session_instance' not in request.app:
        return response
    else:
        try:
            if 'autocommit' in request.app:
                if request.app['autocommit']:
                    log.info('Commiting database transaction via autocommit middleware')
                    request.app['session_instance'].commit()
        except Exception as exc:
            log.exception(exc)
            request.app['session_instance'].rollback()
        finally:
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