#!/usr/bin/python3.6
import argparse
import logging as log

from aiohttp import web

from api.databasemanager import DictionaryDatabaseManager
from api.dictionary import \
    entry, \
    definition, \
    translation, \
    configuration
from api.dictionary import \
    get_dictionary, \
    get_dictionary_xml, \
    get_language_list, \
    download_dictionary, \
    get_inferred_multilingual_dictionary
from api.dictionary.middlewares import \
    json_error_handler, \
    auto_committer

parser = argparse.ArgumentParser(description='Dictionary service')
parser.add_argument('-d', '--db-file', dest='STORAGE', required=False, default='default')
parser.add_argument('-p', '--port', dest='PORT', type=int, default=8001)
parser.add_argument('-l', '--log-file', dest='LOG_FILE', type=str, default='/opt/botjagwar/user_data/dictionary_service.log')
parser.add_argument('--host', dest='HOST', type=str, default='0.0.0.0')
parser.add_argument('--log-level', dest='LOG_LEVEL', type=str, default='debug')
parser.add_argument('--autocommit', dest='autocommit', type=bool, default=True)
parser.add_argument('--commit-every', dest='commit_every', type=int, default=100)

args = parser.parse_args()

WORD_STORAGE = args.STORAGE
HOST = args.HOST
PORT = args.PORT
LOG = args.LOG_FILE
try:
    LOG_LEVEL = log._nameToLevel[args.LOG_LEVEL.upper()]
except KeyError:
    LOG_LEVEL = 10

log.basicConfig(filename=LOG, level=log.DEBUG)
dictionary_db_manager = DictionaryDatabaseManager(database_file=WORD_STORAGE)
routes = web.RouteTableDef()
app = web.Application(middlewares=[
    json_error_handler,
    auto_committer,
])
app['database'] = dictionary_db_manager
app['session_instance'] = dictionary_db_manager.session
app['autocommit'] = args.autocommit
app['commit_every'] = args.commit_every
app['commit_count'] = 0

app.router.add_route('GET', '/languages/list', get_language_list)
app.router.add_route('GET', '/languages/list/download', download_dictionary)

app.router.add_route('GET', '/definition/{definition_id}', definition.get_definition)
app.router.add_route('GET', '/definition_words/{definition_id}', definition.get_definition_with_words)
app.router.add_route('PUT', '/definition/{definition_id}/edit', definition.edit_definition)
#app.router.add_route('POST', '/definition/{language}/create', definition.create_definition)
app.router.add_route('DELETE', '/definition/{definition_id}/delete', definition.delete_definition)
app.router.add_route('POST', '/definition/search', definition.search_definition)

app.router.add_route('GET', '/dictionary/{language}', get_dictionary_xml)
app.router.add_route('GET', '/xml_dictionary/{language}', get_dictionary)
app.router.add_route('GET', '/dictionary/{source}/{bridge}/{target}', get_inferred_multilingual_dictionary)

app.router.add_route('GET', '/entry/{language}/{word}', entry.get_entry)
app.router.add_route('POST', '/entry/{language}/create', entry.add_entry)
app.router.add_route('POST', '/entry/batch', entry.add_batch)
app.router.add_route('PUT', '/entry/{word_id}/edit', entry.edit_entry)
app.router.add_route('DELETE', '/entry/{word_id}/delete', entry.delete_entry)

app.router.add_route('GET', '/translations/{origin}/{target}/{word}', translation.get_translation)
app.router.add_route('GET', '/translations/{origin}/{word}', translation.get_all_translations)
app.router.add_route('GET', '/word/{word_id}', entry.get_word_by_id)

app.router.add_route('GET', '/ping', configuration.pong)
app.router.add_route('POST', '/commit', configuration.do_commit)
app.router.add_route('POST', '/rollback', configuration.do_rollback)
app.router.add_route('PUT', '/configure', configuration.configure_service)


if __name__ == '__main__':
    try:
        app.router.add_routes(routes)
        web.run_app(app, host=HOST, port=PORT, access_log=log)
    except Exception as exc:
        log.exception(exc)
        log.critical("Error occurred while setting up the server")
    finally:
        app['session_instance'].flush()
        app['session_instance'].close()
