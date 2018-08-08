import json
import logging

from aiohttp.web import Response, StreamResponse

from database.dictionary import Word

log = logging.getLogger(__name__)


async def download_dictionary(request) -> StreamResponse:
    session = request.app['session_instance']
    resp = StreamResponse()
    await resp.prepare(request)
    query = session.query(Word).filter(Word.language == request.match_info['language'])
    await resp.write(b'[')
    for element in query.yield_per(100):
        await resp.write(bytes(json.dumps(element.serialise()), 'utf8'))
        await resp.write(b',')

    await resp.write(b']')
    await resp.write_eof()

    return resp


async def get_dictionary(request) -> Response:
    session = request.app['session_instance']
    query = session.query(Word).filter(Word.language == request.match_info['language'])
    definitions = [w.serialise() for w in query.all()]
    if definitions:
        return Response(
            text=json.dumps(definitions),
            status=200)
    else:
        return Response(status=404, content_type='application/json')


async def get_language_list(request) -> Response:
    ret_list = []
    with request.app['database'].engine.connect() as connection:
        query = connection.execute(
            """
            select 
                language, 
                count(id) as nb_entries
            from 
                word
            group by
                language
            order by nb_entries
            desc
            """
        )
        for line in query.fetchall():
            language, nb_entries = line
            ret_list.append({
                'language': language,
                'entries': nb_entries
            })

    return Response(text=json.dumps(ret_list), status=200)