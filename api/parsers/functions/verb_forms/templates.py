# coding: utf8

from api.parsers.constants import NUMBER, MOOD, TENSE, PERSONS, VOICE
from api.parsers.functions.postprocessors import POST_PROCESSORS
from api.parsers.inflection_template import VerbForm


def _parse_es_verb_form_of(parts):
    count = 0
    person = number = tense = mood = None
    for part in parts:
        count += 1
        if part.startswith('pers=') or part.startswith('person='):
            person = part.split('=')[1].strip('}')
        elif part.startswith('number='):
            number = part.split('=')[1].strip('}')
        elif part.startswith('tense='):
            tense = part.split('=')[1].strip('}')
        elif part.startswith('mood='):
            mood = part.split('=')[1].strip('}')
        elif part.startswith('ending='):
            pass
        elif part.startswith('sera='):
            pass
        elif part.startswith('formal='):
            pass
        elif part.startswith('sense='):
            pass

    verb_form = VerbForm('', tense, mood, person, number)
    return verb_form


def parse_es_compound_of(template_expression):
    parts = template_expression.split('|')
    verb_form = _parse_es_verb_form_of(parts)
    verb_form.lemma = parts[3]

    return verb_form


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

    t_name = parts[0]
    if len(parts[1]) in (2, 3):
        lemma = parts[2]
    else:
        lemma = parts[1]

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


def parse_la_verb_form_inflection_of(template_expression):
    post_processor = None

    for char in '{}':
        template_expression = template_expression.replace(char, '')

    parts = template_expression.split('|')
    for tparam in parts:
        if tparam.startswith('lang='):
            post_processor = tparam[5:]
        if tparam.find('=') != -1:
            parts.remove(tparam)

    t_name = parts[0]
    lemma = parts[2]

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
    lemma = parts[-1].replace('}', '')
    if 'region=' in lemma:
        lemma = parts[-2]

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
        elif part.startswith('formal='):
            pass
        elif part.startswith('sense='):
            pass
        elif part.startswith('voseo='):
            pass
        elif part.startswith('participle='):
            pass
        elif part.startswith('region='):
            pass
        elif part.startswith('gender='):
            pass
        elif '=' not in part:
            lemma = part.replace('}', '')

    verb_form = VerbForm(lemma, tense, mood, person, number)
    return verb_form


def parse_ca_verb_form_of(template_expression):
    '{{ca-verb form of|p=2|n=sg|t=impf|m=ind|abordar}}'
    for char in '{}':
        template_expression = template_expression.replace(char, '')

    parts = template_expression.split('|')
    number = person = mood = tense = None
    for tparam in parts:
        if tparam.startswith('p='):
            person = tparam[2:]
        if tparam.startswith('n='):
            number = tparam[2:]
        if tparam.startswith('t='):
            tense = tparam[2:]
        if tparam.startswith('m='):
            mood = tparam[2:]

    if '=' in parts[1]:
        lemma = parts[-1]
    else:
        lemma = parts[1]

    verb_form = VerbForm(lemma, tense, mood, person, number)
    return verb_form


def parse_fi_verb_form_of(template_expression):
    parts = template_expression.split('|')
    voice = 'act'
    person = '0'
    number = 's'
    tense = mood = None
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
    if '=' in lemma:
        lemma = parts[-2]

    verb_form = VerbForm(lemma, tense, mood, person, number, voice)
    return verb_form


def parse_fi_form_of(template_expression):
    '{{fi-form of|aateloida|pr=third-person|pl=singular|mood=indicative|tense=present}}'
    for char in '{}':
        template_expression = template_expression.replace(char, '')

    parts = template_expression.split('|')
    number = person = mood = tense = None
    for tparam in parts:
        if tparam.startswith('pr='):
            person = tparam[3:]
        if tparam.startswith('pl='):
            number = tparam[3:]
        if tparam.startswith('mood='):
            mood = tparam[5:]
        if tparam.startswith('tense='):
            tense = tparam[6:]

    if '=' in parts[1]:
        lemma = parts[-1]
    else:
        lemma = parts[1]

    verb_form = VerbForm(lemma, tense, mood, person, number)
    return verb_form


def parse_de_verb_form_of(template_expression):
    '{{de-verb form of|abfangen|1|s|k2|a}}'
    for char in '{}':
        template_expression = template_expression.replace(char, '')

    parts = template_expression.split('|')
    number = person = mood = tense = ''
    for tparam in parts:
        if tparam in ['1', '2', '3']:
            person = tparam
        elif tparam in NUMBER:
            number = tparam
        elif tparam == 'g':
            tense = 'pres'
        elif tparam == 'v':
            tense = 'pret'
        elif tparam in ('k1', 'k2'):
            mood = 'subj'

    lemma = parts[1]

    verb_form = VerbForm(lemma, tense, mood, person, number)
    return verb_form
