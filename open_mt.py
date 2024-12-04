#!/usr/bin/python3
import json
import logging as log
import traceback
from argparse import ArgumentParser

from aiohttp import web
from aiohttp.web import Response

from api.translation_v2.openmt import OpusMtTransformer

# GLOBAL VARS
verbose = False

parser = ArgumentParser(description="OpenMT translator service")
parser.add_argument("-p", "--port", dest="PORT", type=int, default=8003)
parser.add_argument(
    "-l",
    "--log-file",
    dest="LOG",
    type=str,
    default="/opt/botjagwar/user_data/openmt_translator.log",
)
parser.add_argument("--host", dest="HOST", type=str, default="0.0.0.0")
parser.add_argument(
    "--log-level",
    dest="LOG_LEVEL",
    type=str,
    default="/opt/botjagwar/user_data/entry_translator.log",
)

args = parser.parse_args()

log.basicConfig(filename=args.LOG, level=10)
translator = OpusMtTransformer()
routes = web.RouteTableDef()


@routes.post("/translate/{source_language}/{target_language}")
async def translate(request) -> Response:
    source = request.match_info["source_language"]
    target = request.match_info["target_language"]
    translator.load_model(source, target)
    request_json = await request.json()
    try:
        translation = translator.translate(request_json["text"])
        log.debug('Translating "' + request_json["text"] + '"...')
        log.debug('Translated as "' + translation + '"...')
        returned_json = {
            "type": "translation",
            "text": translation,
            "original": request_json["text"],
        }
        status = 200
    except Exception as error:
        returned_json = {
            "type": "error",
            "status": "translation failed",
            "error_class": error.__class__.__name__,
            "message": error.message if hasattr(error, "message") else "unknown error",
            "traceback": traceback.format_exc(),
        }
        status = error.status_code if hasattr(error, "status_code") else 500
    return Response(
        text=json.dumps(returned_json), status=status, content_type="application/json"
    )


if __name__ == "__main__":
    try:
        app = web.Application()
        app.router.add_routes(routes)
        web.run_app(app, host=args.HOST, port=args.PORT)
    except Exception as exc:
        log.exception(exc)
        log.critical("Error occurred while setting up the server")
