from aiohttp import web
from aiohttp.web import Response
import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from modules.dictionary import get_dictionary
from modules.dictionary import entry, definition, translation

parser = argparse.ArgumentParser(description='Dictionary service')
parser.add_argument('--db-file', dest='STORAGE', required=False)
args = parser.parse_args()

if args.STORAGE:
    STORAGE = args.STORAGE
else:
    DATABASE_STORAGE_INFO_FILE = 'data/storage_info'
    with open(DATABASE_STORAGE_INFO_FILE) as storage_file:
        STORAGE = storage_file.read()

ENGINE = create_engine('sqlite:///%s' % STORAGE)
Base.metadata.create_all(ENGINE)
SessionClass = sessionmaker(bind=ENGINE, autoflush=True)

routes = web.RouteTableDef()

app = web.Application()
app['database_session'] = SessionClass

app.router.add_route('GET', '/definition/{definition_id}', definition.get_definition)
app.router.add_route('POST', '/definition/search', definition.search_definition)
app.router.add_route('DELETE', '/definition/{definition_id}/delete', definition.delete_definition)

app.router.add_route('GET', '/dictionary/{language}', get_dictionary)

app.router.add_route('GET', '/entry/{language}/{word}', entry.get_entry)
app.router.add_route('POST', '/entry/{language}/create', entry.add_entry)
app.router.add_route('PUT', '/entry/{word_id}/edit', entry.edit_entry)
app.router.add_route('DELETE', '/entry/{word_id}/delete', entry.delete_entry)

app.router.add_route('GET', '/translations/{origin}/{target}/{word}', translation.get_translation)
app.router.add_route('GET', '/translations/{origin}/{word}', translation.get_all_translations)


@routes.get('/ping')
async def pong(request):
    Response(status=200)


if __name__ == '__main__':
    app.router.add_routes(routes)
    web.run_app(app, port=8001)
