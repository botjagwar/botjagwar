from api.parsers.inflection_template import NonLemma


def latin_postprocessor(verb_form: NonLemma):
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


def arabic_postprocessor(verb_form: NonLemma):
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


def russian_postprocessor(verb_form: NonLemma):
    new_lemma = verb_form.lemma
    for accented in '́':
        new_lemma = new_lemma.replace(accented, '')

    verb_form.lemma = new_lemma
    return verb_form


POST_PROCESSORS = {
    'ar': arabic_postprocessor,
    'la': latin_postprocessor,
    'ru': russian_postprocessor,
}