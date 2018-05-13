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
    person = number = tense = mood = lemma = None
    count = 0
    for part in parts:
        print(part)
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

    verb_form = VerbForm(lemma, tense, mood, person, number)
    return verb_form
