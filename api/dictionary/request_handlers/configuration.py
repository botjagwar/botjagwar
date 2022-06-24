import json

from aiohttp.web import Response


async def pong(request) -> Response:
    return Response(status=200)


async def do_commit(request) -> Response:
    try:
        request.app['session_instance'].commit()
        request.app['session_instance'].flush()
        return Response(status=200)
    except Exception:
        request.app['session_instance'].rollback()
        return Response(status=200)


async def do_rollback(request) -> Response:
    request.app['session_instance'].rollback()
    return Response(status=200)


async def configure_service(request) -> Response:
    json_text = await request.json()
    data = json.loads(json_text)
    if 'autocommit' in data:
        request.app['autocommit'] = bool(data['autocommit'])

    return Response(status=200)
