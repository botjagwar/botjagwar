#!/usr/bin/python3.6
import json
import os
import sys
import time
import traceback

import pywikibot as pwbot
from aiohttp import web
from aiohttp.web import Response
from pywikibot import Site, Page

from api import entryprocessor
from api.decorator import threaded
from api.translation.core import Translation

# GLOBAL VARS
verbose = False
databases = []
data_file = os.getcwd() + '/conf/entry_translator/'
userdata_file = os.getcwd() + '/user_data/entry_translator/'
translations = Translation()
routes = web.RouteTableDef()


# Throttle Config
def set_throttle(i):
    from pywikibot import throttle
    t = throttle.Throttle(pwbot.Site('mg', 'wiktionary'), mindelay=0, maxdelay=1)
    pwbot.config.put_throttle = 1
    t.setDelays(i)


def _get_page(name, lang):
    page = pwbot.Page(pwbot.Site(lang, 'wiktionary'), name)
    return page


@threaded
def _update_statistics(rc_bot):
    if not rc_bot.stats["edits"] % 5:
        cttime = time.gmtime()[:6]
        rc_bot.chronometer = time.time() - rc_bot.chronometer
        print(("%d/%02d/%02d %02d:%02d:%02d > " % cttime, \
               "Fanovana: %(edits)d; pejy voaforona: %(newentries)d; hadisoana: %(errors)d" % rc_bot.stats \
               + " taha: fanovana %.1f/min" % (60. * (5 / rc_bot.chronometer))))
        rc_bot.chronometer = time.time()


@threaded
def put_deletion_notice(page):
    if not page.exists() or page.isRedirectPage():
        return
    if page.namespace() == 0:
        page_c = page.get()
        page_c += "\n[[sokajy:Pejy voafafa tany an-kafa]]"
        page.put(page_c, "+filazana")


@routes.post("/wiktionary_page/{lang}")
async def handle_wiktionary_page(request):
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
        return
    data = {}
    try:
        await translations.process_wiktionary_wiki_page(page)
    except Exception as e:
        data['traceback'] = traceback.format_exc()
        data['message'] = '' if not hasattr(e, 'message') else getattr(e, 'message')
        response = Response(text=json.dumps(data), status=500, content_type='application/json')
    else:
        response = Response(text=json.dumps(data), status=200, content_type='application/json')
    return response


@routes.get("/wiktionary_page/{language}/{pagename}")
async def get_wiktionary_processed_page(request):
    language = request.match_info['language']
    pagename = request.match_info['pagename']

    wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(language)
    wiktionary_processor = wiktionary_processor_class()
    ret = []

    page = Page(Site(language, 'wiktionary'), pagename)
    wiktionary_processor.process(page)

    for entry in wiktionary_processor.getall():
        word, pos, language_code, definition = entry.to_tuple()
        translation_list = []
        section = dict(
            word=word,
            language=language_code,
            part_of_speech=pos,
            translation=definition[0])

        for translation in wiktionary_processor.retrieve_translations():
            translation_section = dict(
                word=translation.entry,
                language=translation.language,
                part_of_speech=translation.part_of_speech,
                translation=translation.entry_definition[0])
            translation_list.append(translation_section)

        if language_code == language:
            section['translations'] = translation_list
        ret.append(section)

    return Response(text=json.dumps(ret), status=200, content_type='application/json')


args = sys.argv
if __name__ == '__main__':
    try:
        set_throttle(1)
        app = web.Application()
        app.router.add_routes(routes)
        web.run_app(app, host="0.0.0.0", port=8000)
    finally:
        pwbot.stopme()
