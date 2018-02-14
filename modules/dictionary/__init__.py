from aiohttp.web import Response
from database import Word
import json


async def get_dictionary(request):
    session = request.app['session_instance']

    definitions = [w.serialise() for w in session.query(Word).filter(
        Word.language == request.match_info['language']).all()]
    if definitions:
        return Response(
            text=json.dumps(definitions),
            status=200)
    else:
        return Response(status=404, content_type='application/json')