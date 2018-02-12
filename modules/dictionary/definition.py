from aiohttp.web import Response

from database import Definition
import json


async def get_definition(request):
    session_class = request.app['database_session']
    session = session_class()

    definitions = [m.serialise() for m in session.query(Definition).filter(
        Definition.id == request.match_info['definition_id']).all()]
    if definitions:
        return Response(
            text=json.dumps(definitions),
            status=200)
    else:
        return Response(status=404, content_type='application/json')


async def search_definition(request):
    """
    Returns every definition containing the one in 'definition' POST parameter.
    :param request:
    :return:
    """
    session_class = request.app['database_session']
    session = session_class()

    jsondata = await request.json()
    data = json.loads(jsondata)
    definitions = [m.serialise() for m in session.query(
        Definition).filter(Definition.definition.like(data['definition'])).all()]

    return Response(
        text=json.dumps(definitions), status=200, content_type='application/json')


async def delete_definition(request):
    """
    Delete the definition.
    :param request:
    :return:
        HTTP 204 if the definition has been successfully deleted
    """
    # Search if definition already exists.
    session_class = request.app['database_session']
    session = session_class()

    session.query(Definition).filter(
        Definition.id == request.match_info['definition_id']).delete()

    session.commit()
    session.flush()
    return Response(status=204)

