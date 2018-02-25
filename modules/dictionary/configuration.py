from aiohttp.web import Response
import json

async def pong(request):
    Response(status=200)


async def do_commit(request):
    try:
        request.app['session_instance'].commit()
        request.app['session_instance'].flush()
    except Exception:
        request.app['session_instance'].rollback()
        return Response(status=200)


async def do_rollback(request):
    request.app['session_instance'].rollback()
    return Response(status=200)


async def configure_service(request):
    json_text = await request.json()
    data = json.loads(json_text)
    if 'autocommit' in data:
        request.app['autocommit'] = bool(data['autocommit'])

    return Response(status=200)