import json

from aiohttp.web import Response

from api.dictionary.model import Definition
from .routines import save_changes_on_disk


async def get_definition_with_words(request) -> Response:
    session = request.app["session_instance"]

    if definitions := [
        m.serialise_with_words()
        for m in session.query(Definition)
        .filter(Definition.id == request.match_info["definition_id"])
        .all()
    ]:
        return Response(
            text=json.dumps(definitions), status=200, content_type="application/json"
        )

    return Response(status=404, content_type="application/json")


async def edit_definition(request) -> Response:
    session = request.app["session_instance"]
    if definition := (
        session.query(Definition)
        .filter(Definition.id == request.match_info["definition_id"])
        .one()
    ):
        definition_data = await request.json()
        definition.definition = definition_data["definition"]
        definition.definition_language = definition_data["definition_language"]
        await save_changes_on_disk(request.app, session)
        return Response(
            text=json.dumps(definition.serialise()),
            status=200,
            content_type="application/json",
        )

    return Response(status=404, content_type="application/json")


async def get_definition(request) -> Response:
    session = request.app["session_instance"]

    if definitions := [
        m.serialise()
        for m in session.query(Definition)
        .filter(Definition.id == request.match_info["definition_id"])
        .all()
    ]:
        return Response(
            text=json.dumps(definitions), status=200, content_type="application/json"
        )

    return Response(status=404, content_type="application/json")


async def search_definition(request) -> Response:
    """
    Returns every definition containing the one in 'definition' POST parameter.
    :param request:
    :return:
    """
    session = request.app["session_instance"]

    jsondata = await request.json()
    data = json.loads(jsondata)
    definitions = [
        m.serialise()
        for m in session.query(Definition)
        .filter(Definition.definition.like(data["definition"]))
        .all()
    ]

    return Response(
        text=json.dumps(definitions), status=200, content_type="application/json"
    )


async def delete_definition(request) -> Response:
    """
    Delete the definition.
    :param request:
    :return:
        HTTP 204 if the definition has been successfully deleted
    """
    # Search if definition already exists.
    session = request.app["session_instance"]

    session.query(Definition).filter(
        Definition.id == request.match_info["definition_id"]
    ).delete()

    await save_changes_on_disk(request.app, session)
    return Response(status=204)
