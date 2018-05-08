# coding: utf8

from api.parsers.inflection_template import VerbForm
from api.parsers.constants import NUMBER, MOOD, TENSE, PERSONS, VOICE


def latin_postprocessor(verb_form):
    """
    Acts on lemma attributes by removing macron signs from latin long vowels.
    :param verb_form:
    :return:
    """
    new_lemma = verb_form.lemma
    letters = {
        'ā': 'a',
        'ē': 'e',
        'ī': 'i',
        'ō': 'o',
        'ū': 'u',
    }
    for accented, unaccented in letters.items():
        new_lemma = new_lemma.replace(accented, unaccented)

    verb_form.lemma = new_lemma
    return verb_form


def arabic_postprocessor(verb_form):
    """
    Acts on lemma attributes by removing vowel marks on arabic words.
    :param verb_form:
    :return:
    """
    new_lemma = verb_form.lemma
    for accented in 'ًٌٍَُِّْ':
        new_lemma = new_lemma.replace(accented, '')

    verb_form.lemma = new_lemma
    return verb_form


POST_PROCESSORS = {
    'ar': arabic_postprocessor,
    'la': latin_postprocessor,
}


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

