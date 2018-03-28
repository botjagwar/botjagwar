#!/usr/bin/python3.6
from aiohttp import web
import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.dictionary import Base as dictionary_base
from modules.dictionary import get_dictionary
from modules.dictionary import entry, definition, translation, configuration

parser = argparse.ArgumentParser(description='Dictionary service')
parser.add_argument('--db-file', dest='STORAGE', required=False)
args = parser.parse_args()

if args.STORAGE:
    STORAGE = args.STORAGE
else:
    DATABASE_STORAGE_INFO_FILE = 'data/word_database_storage_info'
    with open(DATABASE_STORAGE_INFO_FILE) as storage_file:
        STORAGE = storage_file.read()

ENGINE = create_engine('sqlite:///%s' % STORAGE)
dictionary_base.metadata.create_all(ENGINE)
SessionClass = sessionmaker(bind=ENGINE)

routes = web.RouteTableDef()

app = web.Application()
app['database_session'] = SessionClass
app['session_instance'] = SessionClass()
app['autocommit'] = True


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

app.router.add_route('GET', '/ping', configuration.pong)
app.router.add_route('POST', '/commit', configuration.do_commit)
app.router.add_route('POST', '/rollback', configuration.do_rollback)
app.router.add_route('PUT', '/configure', configuration.configure_service)


if __name__ == '__main__':
    try:
        app.router.add_routes(routes)
        web.run_app(app, host="0.0.0.0", port=8001)
    finally:
        app['session_instance'].flush()
        app['session_instance'].close()
