#!/usr/bin/python3
import argparse
import logging as log

from aiohttp import web

from api.databasemanager import LanguageDatabaseManager
from api.dictionary import configuration
from api.dictionary import languages

parser = argparse.ArgumentParser(description='Language service')
parser.add_argument('--db-file', dest='STORAGE', required=False)
parser.add_argument('-p', '--port', dest='PORT', type=int, default=8003)
args = parser.parse_args()
log.basicConfig(filename='/opt/botjagwar/user_data/language_service.log',level=log.DEBUG)
if args.STORAGE:
    LANGUAGE_STORAGE = args.STORAGE
else:
    LANGUAGE_STORAGE = 'data/language.db'

languge_db_manager = LanguageDatabaseManager(database_file=LANGUAGE_STORAGE)
routes = web.RouteTableDef()
app = web.Application()
app['session_instance'] = languge_db_manager.session
app['autocommit'] = True

app.router.add_route('GET', '/languages', languages.list_languages)

# CRUD
app.router.add_route('GET', '/language/{iso_code}', languages.get_language)
app.router.add_route('POST', '/language/{iso_code}', languages.add_language)
app.router.add_route('PUT', '/language/{iso_code}/edit', languages.edit_language)
app.router.add_route('DELETE', '/language/{iso_code}', languages.delete_language)

# Monitoring
app.router.add_route('GET', '/ping', configuration.pong)
app.router.add_route('POST', '/commit', configuration.do_commit)
app.router.add_route('POST', '/rollback', configuration.do_rollback)
app.router.add_route('PUT', '/configure', configuration.configure_service)


if __name__ == '__main__':
    try:
        app.router.add_routes(routes)
        web.run_app(app, host="0.0.0.0", port=args.PORT, access_log=log)
    except Exception as exc:
        log.exception(exc)
        log.critical("Error occurred while setting up the server")
    finally:
        app['session_instance'].flush()
        app['session_instance'].close()
