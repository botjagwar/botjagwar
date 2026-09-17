import re
from typing import Union

import mwparserfromhell
from mwparserfromhell.nodes import Template
from mwparserfromhell.wikicode import Wikicode

from api.parsers.constants.fr import (
    VOICE,
    MOOD,
    CASES,
    TENSE,
    NUMBER,
    PERSONS,
    DEFINITENESS,
    GENDER,
    POSSESSIVENESS,
)
from api.parsers.inflection_template import VerbForm


DefinitionInput = Union[str, Wikicode]


def _extract_first_positional(template: Template) -> str:
    """Return the first positional argument found on ``template``."""

    for param in template.params:
        name = str(param.name).strip()
        if not name or name.isdigit():
            value = str(param.value).strip()
            if value:
                return value
    return ""


def _extract_lemma(definition_code: Wikicode) -> str:
    """Extract the lemma from templates or wikilinks in ``definition_code``."""

    for template in definition_code.filter_templates():
        if str(template.name).strip() == "lien":
            lemma = _extract_first_positional(template)
            if lemma:
                return lemma

    for wikilink in definition_code.filter_wikilinks():
        target = str(wikilink.title).strip()
        if target:
            return target

    return ""


def parse_fr_definition(definition_source: DefinitionInput):
    """Parse a French verb-form definition using :mod:`mwparserfromhell`."""

    definition_code = (
        definition_source
        if isinstance(definition_source, Wikicode)
        else mwparserfromhell.parse(definition_source)
    )

    definition_text = definition_code.strip_code().lower().replace("''", "")

    returned = VerbForm()

    for determiner in [" du verbe ", " de l’", " de ", " du ", " de la ", " des "]:
        definition_text = definition_text.replace(determiner, " ")

    for voice in VOICE:
        if voice in definition_text:
            returned.voice = VOICE[voice]
            definition_text = definition_text.replace(voice, "")

    for mood in MOOD:
        if mood in definition_text:
            returned.mood = MOOD[mood]
            definition_text = definition_text.replace(mood, "")

    returned.mood = "indicative" if returned.mood is None else returned.mood
    if returned.mood == "imperative":
        returned.tense = "present"

    for cases in CASES:
        if cases in definition_text:
            returned.case = CASES[cases]
            definition_text = definition_text.replace(cases, "")

    for tense in TENSE:
        if tense in definition_text:
            returned.tense = TENSE[tense]
            definition_text = definition_text.replace(tense, "")

    # returned.tense = None if returned.tense is None else returned.tense

    for number in NUMBER:
        if number in definition_text:
            returned.number = NUMBER[number]
            definition_text = definition_text.replace(number, "")

    returned.number = "singular" if returned.number is None else returned.number

    for persons in PERSONS:
        if persons in definition_text:
            returned.person = PERSONS[persons]
            definition_text = definition_text.replace(persons, "")

    for definiteness in DEFINITENESS:
        if definiteness in definition_text:
            returned.definiteness = DEFINITENESS[definiteness]
            definition_text = definition_text.replace(definiteness, "")

    for gender in GENDER:
        if gender in definition_text:
            returned.gender = GENDER[gender]
            definition_text = definition_text.replace(gender, "")

    for possessiveness in POSSESSIVENESS:
        if possessiveness in definition_text:
            returned.possessiveness = POSSESSIVENESS[possessiveness]
            definition_text = definition_text.replace(possessiveness, "")

    lemma = _extract_lemma(definition_code)
    if not lemma:
        if lemma_rgx := re.search(r"\[\[(.*?)]].", str(definition_source)):
            lemma = lemma_rgx.groups()[0]

    returned.lemma = lemma
    return returned
