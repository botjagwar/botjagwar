#!/usr/bin/python3.6
from aiohttp import web
import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.language import Base as LanguageBase
from api.dictionary import languages
from api.dictionary import configuration

parser = argparse.ArgumentParser(description='Language service')
parser.add_argument('--db-file', dest='STORAGE', required=False)
args = parser.parse_args()

if args.STORAGE:
    LANGUAGE_STORAGE = args.STORAGE
else:
    DATABASE_STORAGE_INFO_FILE = 'data/word_database_storage_info'
    with open('data/language_storage_info') as storage_file:
        LANGUAGE_STORAGE = storage_file.read()

LANGUAGE_ENGINE = create_engine('sqlite:///%s' % LANGUAGE_STORAGE)
LanguageBase.metadata.create_all(LANGUAGE_ENGINE)
LanguageSessionClass = sessionmaker(bind=LANGUAGE_ENGINE)


routes = web.RouteTableDef()

app = web.Application()
app['language_base_session'] = LanguageSessionClass
app['language_base_session_instance'] = LanguageSessionClass()
app['autocommit'] = True


app.router.add_route('GET', '/languages', languages.list_languages)

# CRUD
app.router.add_route('GET', '/language/{language}', languages.get_language)
app.router.add_route('POST', '/language/{language}', languages.add_language)
app.router.add_route('PUT', '/language/{language}/edit', languages.edit_language)
app.router.add_route('DELETE', '/language/{language}', languages.delete_language)

# Monitoring
app.router.add_route('GET', '/ping', configuration.pong)
app.router.add_route('POST', '/commit', configuration.do_commit)
app.router.add_route('POST', '/rollback', configuration.do_rollback)
app.router.add_route('PUT', '/configure', configuration.configure_service)


if __name__ == '__main__':
    try:
        app.router.add_routes(routes)
        web.run_app(app, host="0.0.0.0", port=8003)
    finally:
        app['session_instance'].flush()
        app['session_instance'].close()
