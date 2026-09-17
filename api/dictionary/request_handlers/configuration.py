from aiohttp.web import Response


async def pong(request) -> Response:
    return Response(status=200)


async def do_commit(request) -> Response:
    try:
        request.app["session_instance"].commit()
        request.app["session_instance"].flush()
        return Response(status=200)
    except Exception:
        request.app["session_instance"].rollback()
        return Response(status=500)


async def do_rollback(request) -> Response:
    request.app["session_instance"].rollback()
    return Response(status=200)


async def configure_service(request) -> Response:
    data = await request.json()
    if not isinstance(data, dict):
        return Response(status=400)
    if "autocommit" in data:
        if not isinstance(data["autocommit"], bool):
            return Response(status=400)
        request.app["autocommit"] = data["autocommit"]

    return Response(status=200)
