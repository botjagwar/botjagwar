CASES = {
    # very abbreviated forms
    'n': 'nominative',
    'g': 'genitive',
    'd': 'dative',
    'a': 'accusative',
    'l': 'locative',
    'v': 'vocative',

    # abbreviated forms
    'cfin': 'causative final',
    'ade': 'adessive',
    'nom': 'nominative',
    'acc': 'accusative',
    'loc': 'locative',
    'dat': 'dative',
    'gen': 'genitive',
    'ine': 'inessive',
    'del': 'delative',
    'ela': 'elative',
    'ill': 'illative',
    'spe': 'superessive',
    'abl': 'ablative',
    'tran': 'translative',
    'efor': 'formal essive',

    'ins': 'instrumental',
    'pre': 'prepositional',
    'voc': 'vocative',
    'dim': 'diminutive',

    # full forms
    'nominative': 'nominative',
    'genitive': 'genitive',
    'accusative': 'accusative',
    'partitive': 'partitive',
    'inessive': 'inessive',
    'elative': 'elative',
    'illative': 'illative',
    'adessive': 'adessive',
    'ablative': 'ablative',
    'allative': 'allative',
    'essive': 'essive',
    'translative': 'translative',
    'instructive': 'instructive',
    'abessive': 'abessive',
    'comitative': 'comitative',
}

TENSE = {
    'aor': 'aorist',
    'aori': 'aorist',
    'pres': 'present',
    'past': 'past',
    'fut': 'future',
    'futr': 'future',
    'npast': 'non-past',
    'prog': 'progressive',
    'pret': 'preterite',
    'perf': 'perfect',
    'plup': 'pluperfect',
    'pluperf': 'pluperfect',
    'impf': 'imperfect',
    'imperf': 'imperfect',
    'semf': 'semelactive',
    'phis': 'past historic',
    'pfv': 'perfective',
    'perfv': 'perfective',
    'impfv': 'imperfective',

    # full forms
    'present': 'present',
    'imperfect': 'imperfect',
    'preterite': 'preterite',
    'future': 'future',
    'conditional': 'conditional',
}

MOOD = {
    'imp': 'imperative',
    'impr': 'imperative',
    'iter': 'iterative',
    'ind': 'indicative',
    'indc': 'indicative',
    'indic': 'indicative',
    'sub': 'subjunctive',
    'subj': 'subjunctive',
    'cond': 'conditional',
    'opta': 'optative',
    'opt': 'optative',
    'potn': 'potential',
    'juss': 'jussive',
    'coho': 'cohortative',
    'inf': 'infinitive',
    'part': 'participle',
    'ptcp': 'participle',
    'poss': 'possessive',
    'neg': 'negative',
    'conn': 'connegative',
    'conneg': 'connegative',
    'sup': 'supine',

    # full forms
    'gerund': 'gerund',
    'participle': 'participle',
    'conditional': 'conditional',
    'subjunctive': 'subjunctive',
    'indicative': 'indicative',
    'imperative': 'imperative',
}

NUMBER = {
    's': 'singular',
    'sg': 'singular',
    'p': 'plural',
    'd': 'dual',
    't': 'triel',
    'pl': 'plural',
    'pau': 'paucal',
    'sgl': 'singulative',
    'col': 'collective',

    # full forms
    'singular': 'singular',
    'plural': 'plural',
}
GENDER = {
    'm': 'masculine',
    'f': 'feminine',
    'n': 'neuter'
}

VOICE = {
    'act': 'active voice',
    'actv': 'active voice',
    'mid': 'middle voice',
    'midl': 'middle voice',
    'pass': 'passive voice',
    'pasv': 'passive voice',
    'mp': 'mediopassive voice',
    'mpsv': 'mediopassive voice',
}

PERSONS = {
    '1': 'first-person',
    '2': 'second-person',
    '3': 'third-person',
    '4': 'fourth-person',
    '5': 'fifth-person',
    'impers': 'impersonal',

    # full forms
    'first-person': 'first-person',
    'second-person':'second-person',
    'third-person': 'third-person',
}

DEFINITENESS = {
    'def': 'definite',
    'indef': 'indefinite',
    # full forms
    'definite': 'definite',
    'indefinite': 'indefinite',
}

POSSESSIVENESS = {}
for person in PERSONS:
    for number in NUMBER:
        POSSESSIVENESS[person+number] = PERSONS[person] + ' ' + NUMBER[number]
