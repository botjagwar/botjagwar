# -*- coding: utf8 -*-
import time
import sys
import os
import json
import pywikibot as pwbot
from flask import Flask
from modules import service_ports
from modules.decorator import threaded
from modules.translation.core import Translation


# GLOBAL VARS
verbose = False
databases = []
data_file = os.getcwd() + '/conf/dikantenyvaovao/'
userdata_file = os.getcwd() + '/user_data/dikantenyvaovao/'
app = Flask(__name__)
translations = Translation(data_file)


# Throttle Config
def set_throttle(i):
    from pywikibot import throttle
    t = throttle.Throttle(pwbot.Site('mg', 'wiktionary'), mindelay=0, maxdelay=1)
    pwbot.config.put_throttle = 1
    t.setDelays(i)


def _update_unknowns(unknowns):
    f = open(userdata_file + "word_hits", 'a')
    for word, lang in unknowns:
        word += ' [%s]\n' % lang
        print (type(word))
        f.write(word.encode('utf8'))
    f.close()


def _get_page(name, lang):
    page = pwbot.Page(pwbot.Site(lang, 'wiktionary'), name)
    return page


def _update_statistics(rc_bot):
    if not rc_bot.stats["edits"] % 5:
        cttime = time.gmtime()
        rc_bot.chronometer = time.time() - rc_bot.chronometer
        print ("%d/%02d/%02d %02d:%02d:%02d > " % cttime[:6], \
               "Fanovana: %(edits)d; pejy voaforona: %(newentries)d; hadisoana: %(errors)d" % rc_bot.stats \
               + " taha: fanovana %.1f/min" % (60. * (5 / rc_bot.chronometer)))
        rc_bot.chronometer = time.time()


@threaded
def put_deletion_notice(page):
    if not page.exists() or page.isRedirectPage():
        return
    if page.namespace() == 0:
        page_c = page.get()
        page_c += u"\n[[sokajy:Pejy voafafa tany an-kafa]]"
        page.put(page_c, "+filazana")


@app.route("/wiktionary_page/<lang>/<pagename>")
def handle(pagename, lang):
    page = _get_page(pagename, lang)
    if page is None:
        return
    data = {}
    try:
        data['unknowns'], data['new_entries'] = translations.process_wiktionary_page(lang, page)
        _update_unknowns(data['unknowns'])
        response = app.response_class(response=json.dumps(data), status=200, mimetype='application/json')
    except Exception as e:
        data['error'] = e.message
        response = app.response_class(response=json.dumps(data), status=500, mimetype='application/json')
    finally:
        return response


def striplinks(link):
    l = link
    for c in ['[', ']']:
        l = l.replace(c, '')
    return l


args = sys.argv
if __name__ == '__main__':
    try:
        set_throttle(1)
        app.run(host="0.0.0.0", port=service_ports.get_service_port('dikantenyvaovao'))
    finally:
        pwbot.stopme()
