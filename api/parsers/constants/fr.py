CASES = {
    "nominatif": "nominative",
    "génitif": "genitive",
    "accusatif": "accusative",
    "partitif": "partitive",
    "inessif": "inessive",
    "élatif": "elative",
    "illatif": "illative",
    "adessif": "adessive",
    "ablatif": "ablative",
    "allatif": "allative",
    "essif": "essive",
    "translatif": "translative",
    "instructif": "instructive",
    "abessif": "abessive",
    "comitatif": "comitative",
    # Feminine
    "nominative": "nominative",
    "génitive": "genitive",
    "accusative": "accusative",
    "partitive": "partitive",
    "inessive": "inessive",
    "élative": "elative",
    "illative": "illative",
    "adessive": "adessive",
    "ablative": "ablative",
    "allative": "allative",
    "essive": "essive",
    "translative": "translative",
    "instructive": "instructive",
    "abessive": "abessive",
    "comitative": "comitative",
}

TENSE = {
    "aoriste": "aorist",
    "présent": "present",
    "passé simple": "past historic",
    "futur": "future",
    "progressif": "progressive",
    "prétérit": "preterite",
    " parfait": "perfect",
    "plus-que-parfait": "pluperfect",
    "imparfait": "imperfect",
    "semelactif": "semelactive",
    "perfectif": "perfective",
    "imperfectif": "imperfective",
    # Feminine forms of the above
    "future": "future",
    "progressive": "progressive",
    "prétérite": "preterite",
    "parfaite": "perfect",
    "plus-que-parfaite": "pluperfect",
    "imparfaite": "imperfect",
    "semelactive": "semelactive",
    "perfective": "perfective",
    "imperfective": "imperfective",
}

MOOD = {
    "impératif": "imperative",
    "itératif": "iterative",
    "indicatif": "indicative",
    "subjonctif": "subjunctive",
    "conditionnel": "conditional",
    "optatif": "optative",
    "potentiel": "potential",
    "jussif": "jussive",
    "cohortatif": "cohortative",
    "infinitif": "infinitive",
    "participe passé": "past participle",
    "participe présent": "present participle",
    "participe futur": "present participle",
    "possessif": "possessive",
    "négatif": "negative",
    "connégatif": "connegative",
    "supin": "supine",
    "gérondif": "gerund",
    # Feminine forms of the above
    "impérative": "imperative",
    "itérative": "iterative",
    "indicative": "indicative",
    "subjonctive": "subjunctive",
    "conditionelle": "conditional",
    "optative": "optative",
    "potentielle": "potential",
    "jussive": "jussive",
    "cohortative": "cohortative",
    "infinitive": "infinitive",
    "possessive": "participle",
    "négative": "possessive",
    "connégative": "negative",
    "supine": "connegative",
    "gérondive": "gerund",
}

NUMBER = {
    "duel": "dual",
    "duelle": "dual",
    "triel": "triel",
    "trielle": "triel",
    "paucal": "paucal",
    "paucale": "paucal",
    # full forms
    "singulier": "singular",
    "pluriel": "plural",
}
GENDER = {
    "masculin": "masculine",
    "masculine": "masculine",
    "féminin": "feminine",
    "féminine": "feminine",
    "neutre": "neutral",
}

VOICE = {
    "active": "active",
    "actif": "active",
    "médiane": "median",
    "médian": "median",
    "passive": "passive",
    "passif": "passive",
    "médiopassif": "mediopassive",
    "médiopassive": "mediopassive",
}

PERSONS = {
    "première personne": "first-person",
    "deuxième personne": "second-person",
    "(tú)": "second-person (tú)",
    "(vos)": "second-person (vos)",
    "troisième personne": "third-person",
    "quatrième personne": "fourth-person",
    "cinquième personne": "fifth-person",
}

DEFINITENESS = {
    "défini": "definite",
    "indéfini": "indefinite",
}

POSSESSIVENESS = {}
for person in PERSONS:
    for number in NUMBER:
        POSSESSIVENESS[person + number] = PERSONS[person] + " " + NUMBER[number]
