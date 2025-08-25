# coding: utf8
"""Utilities for analysing Spanish verb forms.

This module generates a minimal set of Spanish verb conjugations in
Python.  It supports the simple tenses of the indicative and
subjunctive moods, the simple conditional, the affirmative imperative as
well as gerund and past participle forms.  The implementation is
sufficient for test coverage of regular verbs and the highly irregular
verb ``ser``.
"""

from api.parsers.inflection_template import VerbForm
import unicodedata

# Order of persons corresponding to index of endings below
_PERSONS = ["1", "2", "3", "1", "2", "3"]
_NUMBERS = ["singular", "singular", "singular", "plural", "plural", "plural"]

# Mapping of moods to supported tenses
MOOD_TENSES = {
    "indicative": ["present", "preterite", "imperfect", "future", "conditional"],
    "subjunctive": ["present", "imperfect"],
}

# Endings for regular verbs, indexed by (mood, tense, conjugation)
ENDINGS = {
    ("indicative", "present", "ar"): ["o", "as", "a", "amos", "áis", "an"],
    ("indicative", "present", "er"): ["o", "es", "e", "emos", "éis", "en"],
    ("indicative", "present", "ir"): ["o", "es", "e", "imos", "ís", "en"],
    ("indicative", "preterite", "ar"): ["é", "aste", "ó", "amos", "asteis", "aron"],
    ("indicative", "preterite", "er"): ["í", "iste", "ió", "imos", "isteis", "ieron"],
    ("indicative", "preterite", "ir"): ["í", "iste", "ió", "imos", "isteis", "ieron"],
    ("indicative", "imperfect", "ar"): ["aba", "abas", "aba", "ábamos", "abais", "aban"],
    ("indicative", "imperfect", "er"): ["ía", "ías", "ía", "íamos", "íais", "ían"],
    ("indicative", "imperfect", "ir"): ["ía", "ías", "ía", "íamos", "íais", "ían"],
    ("indicative", "future", "ar"): ["é", "ás", "á", "emos", "éis", "án"],
    ("indicative", "future", "er"): ["é", "ás", "á", "emos", "éis", "án"],
    ("indicative", "future", "ir"): ["é", "ás", "á", "emos", "éis", "án"],
    ("indicative", "conditional", "ar"): ["ía", "ías", "ía", "íamos", "íais", "ían"],
    ("indicative", "conditional", "er"): ["ía", "ías", "ía", "íamos", "íais", "ían"],
    ("indicative", "conditional", "ir"): ["ía", "ías", "ía", "íamos", "íais", "ían"],
    ("subjunctive", "present", "ar"): ["e", "es", "e", "emos", "éis", "en"],
    ("subjunctive", "present", "er"): ["a", "as", "a", "amos", "áis", "an"],
    ("subjunctive", "present", "ir"): ["a", "as", "a", "amos", "áis", "an"],
    ("subjunctive", "imperfect", "ar"): ["ara", "aras", "ara", "áramos", "arais", "aran"],
    ("subjunctive", "imperfect", "er"): ["iera", "ieras", "iera", "iéramos", "ierais", "ieran"],
    ("subjunctive", "imperfect", "ir"): ["iera", "ieras", "iera", "iéramos", "ierais", "ieran"],
}

# Imperative endings for regular verbs (tu, usted, nosotros, vosotros, ustedes)
IMPERATIVE_ENDINGS = {
    "ar": ["a", "e", "emos", "ad", "en"],
    "er": ["e", "a", "amos", "ed", "an"],
    "ir": ["e", "a", "amos", "id", "an"],
}
IMPERATIVE_PRONOUNS = ["tu", "usted", "nosotros", "vosotros", "ustedes"]
IMPERATIVE_PERSON_NUMBER = {
    "tu": ("2", "singular"),
    "usted": ("3", "singular"),
    "nosotros": ("1", "plural"),
    "vosotros": ("2", "plural"),
    "ustedes": ("3", "plural"),
}

# Irregular forms for verbs we explicitly support
IRREGULAR_FORMS = {
    "ser": {
        ("indicative", "present"): ["soy", "eres", "es", "somos", "sois", "son"],
        ("indicative", "preterite"): ["fui", "fuiste", "fue", "fuimos", "fuisteis", "fueron"],
        ("indicative", "imperfect"): ["era", "eras", "era", "éramos", "erais", "eran"],
        ("indicative", "future"): ["seré", "serás", "será", "seremos", "seréis", "serán"],
        ("indicative", "conditional"): ["sería", "serías", "sería", "seríamos", "seríais", "serían"],
        ("subjunctive", "present"): ["sea", "seas", "sea", "seamos", "seáis", "sean"],
        ("subjunctive", "imperfect"): ["fuera", "fueras", "fuera", "fuéramos", "fuerais", "fueran"],
        ("imperative", "affirmative"): ["sé", "sea", "seamos", "sed", "sean"],
    }
}

IRREGULAR_GERUNDS = {"ser": "siendo"}
IRREGULAR_PARTICIPLES = {"ser": "sido"}

CLITIC_PRONOUNS = [
    "me",
    "te",
    "se",
    "lo",
    "la",
    "le",
    "los",
    "las",
    "les",
    "nos",
    "os",
]


def _strip_accents(text: str) -> str:
    chars = []
    for c in unicodedata.normalize("NFD", text):
        if c == "\u0303":  # keep tilde for ñ
            chars.append(c)
        elif unicodedata.category(c) == "Mn":
            continue
        else:
            chars.append(c)
    return unicodedata.normalize("NFC", "".join(chars))


def _strip_clitic_pronouns(word: str) -> str:
    for pron2 in CLITIC_PRONOUNS:
        if word.endswith(pron2):
            base = word[: -len(pron2)]
            for pron1 in CLITIC_PRONOUNS:
                if base.endswith(pron1):
                    return base[: -len(pron1)]
            return base
    return word


def _regular_gerund(lemma: str) -> str:
    if lemma.endswith("ar"):
        return lemma[:-2] + "ando"
    if lemma.endswith("er") or lemma.endswith("ir"):
        return lemma[:-2] + "iendo"
    return ""


def _regular_participle(lemma: str) -> str:
    if lemma.endswith("ar"):
        return lemma[:-2] + "ado"
    if lemma.endswith("er") or lemma.endswith("ir"):
        return lemma[:-2] + "ido"
    return ""


def get_es_verb_form(word: str, lemma: str) -> VerbForm:
    """Return a :class:`VerbForm` representing *word* of *lemma*.

    The function searches through the supported conjugation tables for a
    match with ``word``.  If no match is found, a :class:`VerbForm` with
    only the lemma is returned.
    """
    all_forms_computed = []
    if lemma.endswith("se"):
        pronominal = True
        lemma = lemma[:-2]
    else:
        pronominal = False

    conj = lemma[-2:]
    stem = lemma[:-2]
    irregular = IRREGULAR_FORMS.get(lemma, {})

    # Finite forms
    for mood, tenses in MOOD_TENSES.items():
        for tense in tenses:
            if (mood, tense) in irregular:
                forms = irregular[(mood, tense)]
            else:
                endings = ENDINGS[(mood, tense, conj)]
                base = lemma if tense in {"future", "conditional"} else stem
                forms = [base + e for e in endings]
            for i, form in enumerate(forms):
                all_forms_computed.append(form)
                if form == word:
                    if pronominal:
                        return VerbForm(lemma + 'se', tense, mood, _PERSONS[i], _NUMBERS[i])
                    else:
                        return VerbForm(lemma, tense, mood, _PERSONS[i], _NUMBERS[i])

    # Imperative
    if ("imperative", "affirmative") in irregular:
        forms = irregular[("imperative", "affirmative")]
    else:
        endings = IMPERATIVE_ENDINGS[conj]
        forms = [stem + e for e in endings]
    for pronoun, form in zip(IMPERATIVE_PRONOUNS, forms):
        if form == word:
            person, number = IMPERATIVE_PERSON_NUMBER[pronoun]
            if pronominal:
                return VerbForm(lemma + 'se', "affirmative", "imperative", person, number)
            else:
                return VerbForm(lemma, "affirmative", "imperative", person, number)

    # Gerund
    ger = IRREGULAR_GERUNDS.get(lemma, _regular_gerund(lemma))
    if word == ger:
        if pronominal:
            return VerbForm(lemma + 'se', None, "gerund")
        else:
            return VerbForm(lemma, None, "gerund")
    stripped = _strip_clitic_pronouns(word)
    if _strip_accents(stripped) == ger:
        if pronominal:
            return VerbForm(lemma + 'se', None, "gerund")
        else:
            return VerbForm(lemma, None, "gerund")

    # Past participle (masculine singular)
    part = IRREGULAR_PARTICIPLES.get(lemma, _regular_participle(lemma))
    if word == part:
        return VerbForm(lemma, "past", "participle")

    return VerbForm(lemma)
