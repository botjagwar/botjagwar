# coding: utf8

from api.parsers.inflection_template import VerbForm
from api.parsers.constants import NUMBER, MOOD, TENSE, PERSONS, VOICE
from api.parsers.functions.postprocessors import POST_PROCESSORS


def parse_verb_form_inflection_of(template_expression):
    post_processor = None

    for char in '{}':
        template_expression = template_expression.replace(char, '')

    parts = template_expression.split('|')
    for tparam in parts:
        if tparam.startswith('lang='):
            post_processor = tparam[5:]
        if tparam.find('=') != -1:
            parts.remove(tparam)

    t_name, lemma, = parts[:2]

    person = number = tense = mood = None
    voice = 'act'
    for pn in parts:
        if pn in NUMBER:
            number = pn
        elif pn in MOOD:
            mood = pn
        elif pn in TENSE:
            tense = pn
        elif pn in PERSONS:
            person = pn
        elif pn in VOICE:
            voice = pn

    verb_form = VerbForm(lemma, tense, mood, person, number, voice)
    if post_processor is not None and post_processor in POST_PROCESSORS:
        verb_form = POST_PROCESSORS[post_processor](verb_form)

    return verb_form


def parse_es_verb_form_of(template_expression):
    parts = template_expression.split('|')
    person = number = tense = mood = None
    count = 0
    for part in parts:
        count += 1
        if part.startswith('pers=') or part.startswith('person='):
            person = part.split('=')[1]
        elif part.startswith('number='):
            number = part.split('=')[1]
        elif part.startswith('tense='):
            tense = part.split('=')[1]
        elif part.startswith('mood='):
            mood = part.split('=')[1]
        elif part.startswith('ending='):
            pass
        elif part.startswith('sera='):
            pass

    lemma = parts[-1].replace('}', '')
    if 'region=' in lemma:
        lemma = parts[-2]

    verb_form = VerbForm(lemma, tense, mood, person, number)
    return verb_form


def parse_fi_verb_form_of(template_expression):
    parts = template_expression.split('|')
    voice = 'act'
    person = number = tense = mood = None
    count = 0
    for part in parts:
        count += 1
        if part.startswith('pn='):
            pn = part.split('=')[1]
            if pn == '1s':
                person = '1'
                number = 's'
            elif pn == '2s':
                person = '2'
                number = 's'
            elif pn == '3s':
                person = '3'
                number = 's'
            elif pn == '1p':
                person = '1'
                number = 'p'
            elif pn == '2p':
                person = '2'
                number = 'p'
            elif pn == '3p':
                person = '3'
                number = 'p'
            elif pn == 'pasv' or pn == 'pass':
                voice = 'pass'

        if part.startswith('tm='):
            tense_mood = part.split('=')[1]
            if tense_mood == 'pres':
                mood = 'ind'
                tense = 'pres'
            elif tense_mood == 'past':
                mood = 'ind'
                tense = 'past'
            elif tense_mood == 'cond':
                mood = 'cond'
                tense = 'pres'
            elif tense_mood == 'impr':
                mood = 'imp'
                tense = 'pres'
            elif tense_mood == 'potn':
                mood = 'pot'
                tense = 'pres'

    lemma = parts[-1].replace('}', '')
    if 'region=' in lemma:
        lemma = parts[-2]

    verb_form = (lemma, tense, mood, person, number, voice)
    return verb_form
