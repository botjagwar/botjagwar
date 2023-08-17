import re

from api.parsers.constants.fr import \
    CASES, NUMBER, PERSONS, DEFINITENESS, GENDER, POSSESSIVENESS
from api.parsers.inflection_template import NounForm


def parameterized_parse_fr_definition(form_class=NounForm):
    def parse_fr_definition(definition_line):
        definition_line = definition_line.lower()
        definition_line = definition_line.replace("''", '')

        returned = form_class()

        for determiner in [
            ' du verbe ', ' de l’', ' de ', ' du ', ' de la ', ' des ']:
            definition_line = definition_line.replace(determiner, ' ')

        for cases in CASES:
            if cases in definition_line:
                returned.case = CASES[cases]
                definition_line = definition_line.replace(cases, '')

        # returned.tense = None if returned.tense is None else returned.tense

        for number in NUMBER:
            if number in definition_line:
                returned.number = NUMBER[number]
                definition_line = definition_line.replace(number, '')

        returned.number = 'singular' if returned.number is None else returned.number

        for persons in PERSONS:
            if persons in definition_line:
                returned.person = PERSONS[persons]
                definition_line = definition_line.replace(persons, '')

        for definiteness in DEFINITENESS:
            if definiteness in definition_line:
                returned.definiteness = DEFINITENESS[definiteness]
                definition_line = definition_line.replace(definiteness, '')

        for gender in GENDER:
            if gender in definition_line:
                returned.gender = GENDER[gender]
                definition_line = definition_line.replace(gender, '')

        for possessiveness in POSSESSIVENESS:
            if possessiveness in definition_line:
                returned.possessiveness = POSSESSIVENESS[possessiveness]
                definition_line = definition_line.replace(possessiveness, '')

        definition_line = definition_line.strip()

        # Template links are already removed at this stage, so finding the '{{' and '}}' are
        #   not needed.
        lemma_rgx = re.search('lien\|(.*)\|(.*).', definition_line)
        if lemma_rgx:
            lemma = lemma_rgx.groups()[0]
        else:
            lemma_rgx = re.search('\[\[(.*)]].', definition_line)
            if lemma_rgx:
                lemma = lemma_rgx.groups()[0]
            else:
                lemma = ''
        returned.lemma = lemma
        return returned

    return parse_fr_definition
