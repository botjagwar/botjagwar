#!/usr/bin/python3
import json
import logging as log
import time
import traceback
from argparse import ArgumentParser

import pywikibot as pwbot
from aiohttp import web
from aiohttp.web import Response

from api import entryprocessor
from api.decorator import threaded
from api.translation_v2.core import Translation
from api.translation_v2.publishers import WiktionaryRabbitMqPublisher
from redis_wikicache import RedisSite as Site, RedisPage as Page

# GLOBAL VARS
verbose = False
databases = []

parser = ArgumentParser(description="Entry translator service")
parser.add_argument('-p', '--port', dest='PORT', type=int, default=8000)
parser.add_argument(
    '-l',
    '--log-file',
    dest='LOG',
    type=str,
    default='/opt/botjagwar/user_data/entry_translator.log')
parser.add_argument('--host', dest='HOST', type=str, default='0.0.0.0')
parser.add_argument(
    '--log-level',
    dest='LOG_LEVEL',
    type=str,
    default='/opt/botjagwar/user_data/entry_translator.log')

args = parser.parse_args()

try:
    LOG_LEVEL = log._nameToLevel[args.LOG_LEVEL.upper()]
except KeyError:
    LOG_LEVEL = 10

log.basicConfig(filename=args.LOG, level=LOG_LEVEL)
translations = Translation()
routes = web.RouteTableDef()
rabbitmq_publisher = WiktionaryRabbitMqPublisher()


# Throttle Config
def set_throttle(i):
    from pywikibot import throttle
    t = throttle.Throttle(
        pwbot.Site(
            'mg',
            'wiktionary'),
        mindelay=0,
        maxdelay=1)
    pwbot.config.put_throttle = 1
    t.setDelays(i)


def _get_page(name, lang):
    page = Page(Site(lang, 'wiktionary'), name)
    return page


@threaded
def _update_statistics(rc_bot):
    if not rc_bot.stats["edits"] % 5:
        cttime = time.gmtime()[:6]
        rc_bot.chronometer = time.time() - rc_bot.chronometer
        log.debug(("%d/%02d/%02d %02d:%02d:%02d > " %
                   cttime, "Fanovana: %(edits)d; pejy voaforona: %(newentries)d; hadisoana: %(errors)d" %
                   rc_bot.stats + " taha: fanovana %.1f/min" %
                   (60. * (5 / rc_bot.chronometer))))
        rc_bot.chronometer = time.time()


@threaded
def put_deletion_notice(page):
    if not page.exists() or page.isRedirectPage():
        return
    if page.namespace() == 0:
        page_c = page.get()
        page_c += "\n[[sokajy:Pejy voafafa tany an-kafa]]"
        page.put(page_c, "+filazana")


@routes.post("/wiktionary_page_async/{lang}")
async def handle_wiktionary_page(request) -> Response:
    """
    Handle a Wiktionary page, attempts to translate the wiktionary page's content and
    uploads it to the Malagasy Wiktionary.
    <lang>: Wiktionary edition to look up on.
    :return: 200 if everything worked with the list of database lookups including translations,
    500 if an error occurred
    """
    data = await request.json()
    pagename = data['title']
    page = _get_page(pagename, request.match_info['lang'])
    if page is None:
        return Response()

    data = {}
    publish = None

    @threaded
    def task():
        try:
            translations.process_wiktionary_wiki_page(page, custom_publish_function=publish)
        except Exception as e:
            log.exception(e)
            data['traceback'] = traceback.format_exc()
            data['message'] = '' if not hasattr(e, 'message') else getattr(e, 'message')

    task()
    # cooldown
    return Response(
        text=json.dumps({'message': 'task successfully pushed.'}),
        status=200,
        content_type='application/json'
    )


@routes.post("/wiktionary_page_async_new/{lang}")
async def handle_wiktionary_page(request) -> Response:
    """
    Handle a Wiktionary page, attempts to translate the wiktionary page's content and
    uploads it to the Malagasy Wiktionary.
    <lang>: Wiktionary edition to look up on.
    :return: 200 if everything worked with the list of database lookups including translations,
    500 if an error occurred
    """
    data = await request.json()
    pagename = data['title']
    page = _get_page(pagename, request.match_info['lang'])
    if page is None:
        return Response()

    data = {}
    publish = rabbitmq_publisher.publish_to_wiktionary(translations)

    @threaded
    def task():
        try:
            translations.process_wiktionary_wiki_page(page, custom_publish_function=publish)
        except Exception as e:
            log.exception(e)
            data['traceback'] = traceback.format_exc()
            data['message'] = '' if not hasattr(e, 'message') else getattr(e, 'message')

    task()
    # cooldown
    return Response(
        text=json.dumps({'message': 'task successfully pushed.'}),
        status=200,
        content_type='application/json'
    )


@routes.post("/wiktionary_page/{lang}")
async def handle_wiktionary_page(request) -> Response:
    """
    Handle a Wiktionary page, attempts to translate the wiktionary page's content and
    uploads it to the Malagasy Wiktionary.
    <lang>: Wiktionary edition to look up on.
    :return: 200 if everything worked with the list of database lookups including translations,
    500 if an error occurred
    """

    data = await request.json()
    pagename = data['title']
    page = _get_page(pagename, request.match_info['lang'])
    if page is None:
        return Response()
    data = {}
    try:
        translations.process_wiktionary_wiki_page(page)
    except Exception as e:
        log.exception(e)
        data['traceback'] = traceback.format_exc()
        data['message'] = '' if not hasattr(e, 'message') else getattr(e, 'message')
        response = Response(
            text=json.dumps(data),
            status=500,
            content_type='application/json')
    else:
        response = Response(
            text=json.dumps(data),
            status=200,
            content_type='application/json')
    return response


@routes.get("/translation/{language}/{pagename}")
async def get_wiktionary_page_translation(request) -> Response:
    language = request.match_info['language']
    pagename = request.match_info['pagename']
    data = {}
    try:
        wiktionary_processor_class = entryprocessor.\
            WiktionaryProcessorFactory.create(language)
        wiktionary_processor = wiktionary_processor_class()
        wiki_page = _get_page(pagename, language)
        wiktionary_processor.set_text(wiki_page.get())
        wiktionary_processor.set_title(wiki_page.title())
        data = translations.translate_wiktionary_page(wiktionary_processor)
    except Exception as e:
        log.exception(e)
        data['traceback'] = traceback.format_exc()
        data['type'] = 'error'
        data['message'] = 'unknown error' if not hasattr(e, 'message') else getattr(e, 'message')
        response = Response(
            text=json.dumps(data),
            status=500,
            content_type='application/json')
    else:
        response = Response(
            text=json.dumps([d.serialise() for d in data]),
            status=200,
            content_type='application/json')
    return response


@routes.get("/wiktionary_page/{language}/{pagename}")
async def get_wiktionary_processed_page(request) -> Response:
    language = request.match_info['language']
    pagename = request.match_info['pagename']

    wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(
        language)
    wiktionary_processor = wiktionary_processor_class()
    ret = []

    page = Page(Site(language, 'wiktionary'), pagename)
    wiktionary_processor.process(page)

    for entry in wiktionary_processor.get_all_entries(
        get_additional_data=True,
        cleanup_definitions=True,
        advanced=True
    ):
        translation_list = []
        definitions = []
        for d in entry.definitions:
            definitions.append(wiktionary_processor.advanced_extract_definition(entry.part_of_speech, d))

        entry.definitions = definitions
        section = entry.serialise()

        for translation in wiktionary_processor.retrieve_translations():
            if translation.part_of_speech == entry.part_of_speech:
                translation_list.append(translation.serialise())

        if entry.language == language:
            section['translations'] = translation_list
        ret.append(section)

    return Response(
        text=json.dumps(ret),
        status=200,
        content_type='application/json')


if __name__ == '__main__':
    try:
        import os

        current_pid = os.getpid()
        with open('/tmp/entry_translator.pid', 'w') as f:
            f.write(str(current_pid))

        set_throttle(1)
        app = web.Application()
        app.router.add_routes(routes)
        web.run_app(app, host=args.HOST, port=args.PORT)
    except Exception as exc:
        log.exception(exc)
        log.critical("Error occurred while setting up the server")
    finally:
        pwbot.stopme()
