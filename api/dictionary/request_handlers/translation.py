import json

from aiohttp.web import Response

from api.dictionary.model import Word

# Do not translate with form-of entries as they depend on main entries
FORM_OF_BLACKLIST = ["e-ana", "e-mat", "e-mpam"]


async def get_translation(request) -> Response:
    session = request.app["session_instance"]
    origin, target = request.match_info["origin"], request.match_info["target"]

    words = [
        w.serialise()
        for w in session.query(Word)
        .filter(Word.language == origin)
        .filter(Word.word == request.match_info["word"])
        .all()
    ]
    translations = []
    for word in words:
        definitions = word["definitions"]
        for definition in definitions:
            if definition["language"] == target:
                definition["part_of_speech"] = word["part_of_speech"]
                if word["part_of_speech"] not in FORM_OF_BLACKLIST:
                    translations.append(definition)
                else:
                    print(definition)

    return Response(
        text=json.dumps(translations), status=200, content_type="application/json"
    )


async def get_all_translations(request) -> Response:
    """
    Find all translations for the given word in the given language
    :return:
    """
    session = request.app["session_instance"]
    origin = request.match_info["origin"]

    words = [
        w.serialise()
        for w in session.query(Word)
        .filter(Word.language == origin)
        .filter(Word.word == request.match_info["word"])
        .all()
    ]
    translations = []
    for word in words:
        definitions = word["definitions"]
        for definition in definitions:
            definition["word_pos"] = word["part_of_speech"]
            translations.append(definition)

    return Response(
        text=json.dumps(translations), status=200, content_type="application/json"
    )
