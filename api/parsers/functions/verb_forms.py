# coding: utf8

from api.parsers.inflection_template import VerbForm
from api.parsers.constants import NUMBER, MOOD, TENSE, PERSONS, VOICE

def parse_verb_form_inflection_of(template_expression):
    for char in '{}':
        template_expression = template_expression.replace(char, '')
    parts = template_expression.split('|')
    for tparam in parts:
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

    return VerbForm(lemma, tense, mood, person, number, voice)


