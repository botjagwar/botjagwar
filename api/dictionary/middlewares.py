import json
import logging

from aiohttp.web import Response
from aiohttp.web import middleware

log = logging.getLogger(__name__)


@middleware
async def auto_committer(request, handler) -> Response:
    try:
        response = await handler(request)
        if request.method.lower() in ['post', 'put']:
            if request.app['autocommit']:
                if  request.app['commit_count'] >= request.app['commit_every']:
                    if 400 <= response.status < 600:
                        request.app['session_instance'].rollback()
                        log.info('automatically rolled back changes to database')
                    else:
                        request.app['session_instance'].commit()
                        log.info('automatically committed changes to database')

                    request.app['commit_count'] = 0
                else:
                    request.app['commit_count'] += 1
    except Exception as e:
        request.app['session_instance'].rollback()
        raise e
    else:
        return response


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
        response.text = json.dumps(data)
    return response
