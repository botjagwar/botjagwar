# -*- coding: utf8 -*-
import os
import sys
import time
import json
import pywikibot as pwbot
from flask import Flask, request
import traceback


from modules import service_ports
from modules import entryprocessor
from modules.broken_database import Database
from modules.broken_database.word import WordDatabase
from modules.decorator import threaded
from modules.translation.core import Translation

from pywikibot import Site, Page

from sqlite3 import DataError, IntegrityError, ProgrammingError


# GLOBAL VARS
verbose = False
databases = []
data_file = os.getcwd() + '/conf/dikantenyvaovao/'
userdata_file = os.getcwd() + '/user_data/dikantenyvaovao/'
app = Flask(__name__)
translations = Translation(data_file)
languages = {
    'en': 'anglisy',
    'fr': 'frantsay'
}

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
        print((type(word)))
        f.write(word.encode('utf8'))
    f.close()


def _get_page(name, lang):
    page = pwbot.Page(pwbot.Site(lang, 'wiktionary'), name)
    return page


@threaded
def _update_statistics(rc_bot):
    if not rc_bot.stats["edits"] % 5:
        cttime = time.gmtime()
        rc_bot.chronometer = time.time() - rc_bot.chronometer
        print(("%d/%02d/%02d %02d:%02d:%02d > " % cttime[:6], \
               "Fanovana: %(edits)d; pejy voaforona: %(newentries)d; hadisoana: %(errors)d" % rc_bot.stats \
               + " taha: fanovana %.1f/min" % (60. * (5 / rc_bot.chronometer))))
        rc_bot.chronometer = time.time()


def _get_word_id(word, lang_code):
    """
    Gets the word ID
    :param word: word
    :param language: ISO language code of the language the word belongs to
    :return: the word ID
    """
    word_db = Database(table="%s" % languages[lang_code])
    results = word_db.read({
        languages[lang_code] : word
    }, select="%s_wID" % lang_code)
    if results:
        return results
    else:
        return ()


@threaded
def put_deletion_notice(page):
    if not page.exists() or page.isRedirectPage():
        return
    if page.namespace() == 0:
        page_c = page.get()
        page_c += "\n[[sokajy:Pejy voafafa tany an-kafa]]"
        page.put(page_c, "+filazana")


@app.route("/wiktionary_page/<lang>", methods=['POST'])
def handle_wiktionary_page(lang):
    """
    Handle a Wiktionary page, attempts to translate the wiktionary page's content and
    uploads it to the Malagasy Wiktionary.
    :param lang: Wiktionary edition to look up on.
    :return: 200 if everything worked with the list of database lookups including translations,
    500 if an error occurred
    """

    data = json.loads(request.get_data())
    pagename = data['title']
    page = _get_page(pagename, lang)
    if page is None:
        return
    data = {}
    try:
        data['unknowns'], data['new_entries'] = translations.process_wiktionary_wiki_page(page)
        _update_unknowns(data['unknowns'])
    except Exception as e:
        traceback.print_exc()
        data['traceback'] = traceback.format_exc()
        data['message'] = e.message
        response = app.response_class(response=json.dumps(data), status=500, mimetype='application/json')
    else:
        response = app.response_class(response=json.dumps(data), status=200, mimetype='application/json')

    return response


@app.route("/wiktionary_page/<language>/<pagename>", methods=['GET'])
def get_wiktionary_processed_page(language, pagename):
    wiktionary_processor_class = entryprocessor.WiktionaryProcessorFactory.create(language)
    wiktionary_processor = wiktionary_processor_class()
    ret = []

    page = Page(Site(language, 'wiktionary'), pagename)
    wiktionary_processor.process(page)

    for entry in wiktionary_processor.getall():
        word, pos, language_code, translation = entry
        translation_list = []
        section = dict(
            word=word,
            language=language_code,
            part_of_speech=pos,
            translation=translation)
        for translation in wiktionary_processor.retrieve_translations():
            translation_word, translation_pos, translation_language, translation = translation
            translation_section = dict(
                word=translation_word,
                language=translation_language,
                part_of_speech=translation_pos,
                translation=translation)
            translation_list.append(translation_section)

        if language_code == language:
            section['translations'] = translation_list
        ret.append(section)

    return app.response_class(response=json.dumps(ret), status=200, mimetype='application/json')


@app.route("/translate/<lang>", methods=["PUT"])
def handle_translate_word(lang):
    """
    POST Service to translate a given word to a native language
    Returns 500 if translation exists or if an error has occurred, 200 otherwise
    :param lang:
    :return:
    """
    data = json.loads(request.get_data())
    word = data["word"]
    translation = data["translation"]
    part_of_speech = data["POS"]
    dry_run = data["dryrun"]

    translation_db = WordDatabase()
    translation_write_db = Database(table="%s_malagasy" % languages[lang])

    if (translation_db.exists_in_specialised_dictionary(word, lang, part_of_speech)
        or translation_db.exists(word, lang, part_of_speech)):
        response = app.response_class(
            response=json.dumps({'message': 'Word already exists and has been translated'}),
            status=520, mimetype='application/json')
    else:
        try:
            added = []
            for id_ in _get_word_id(word, lang):
                translation = db.escape_string(translation.encode('utf8'))
                translation = translation.decode('utf8')
                sql_data = {
                    "%s_wID" % lang: str(id_[0]),
                    "mg": translation
                }
                added.append(sql_data)
                translation_write_db.insert(sql_data, dry_run=dry_run)
        except (DataError, IntegrityError, ProgrammingError) as e:
            response = app.response_class(
                response=json.dumps({'message': e.message}),
                status=500, mimetype='application/json')
        else:
            if not added:
                response = app.response_class(
                    response=json.dumps({'message': 'No addition performed'}),
                    status=324, mimetype='application/json')
            else:
                response = app.response_class(
                    response=json.dumps({'added': added}),
                    status=200, mimetype='application/json')

    return response


@app.route('/dictionary/<origin>/<target>', methods=['GET'])
def handle_get_specialised_dictionary(origin, target):
    translations_db = WordDatabase()
    result = translations_db.DB.raw_query(
        "select * from data_botjagwar.%s_%s"
        % (db.escape_string(origin), db.escape_string(target)))
    return app.response_class(
        response=json.dumps(result),
        status=200, mimetype='application/json')


args = sys.argv
if __name__ == '__main__':
    try:
        set_throttle(1)
        app.run(host="0.0.0.0", port=service_ports.get_service_port('dikantenyvaovao'))
    finally:
        pwbot.stopme()
