from aiohttp.web import json_response
from database.language import Language


async def list_languages(request):
    session = request.app['language_base_session_instance']
    languages = [m.serialise() for m in session.query(Language).all()]
    return json_response(languages)


async def add_language(request):
    pass


async def get_language(request):
    pass


async def edit_language(request):
    pass


async def delete_language(request):
    pass


