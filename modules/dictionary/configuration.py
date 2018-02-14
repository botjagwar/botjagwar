from aiohttp.web import Response
import json

async def pong(request):
    Response(status=200)


async def do_commit(request):
    request.app['session_instance'].flush()
    return Response(status=200)


async def configure_service(request):
    json_text = await request.json()
    data = json.loads(json_text)
    if 'autocommit' in data and data['autocommit'] == True:
        request.app['autocommit'] = True

    return Response(status=200)