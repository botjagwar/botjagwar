# coding: utf8

from api.parsers.inflection_template import VerbForm


def parse_verb_form_inflection_of(template_expression):
    for char in '{}':
        template_expression = template_expression.replace(char, '')
    parts = template_expression.split('|')
    for tparam in parts:
        if tparam.find('=') != -1:
            parts.remove(tparam)
    t_name, lemma, _, case_name, number_ = parts[:5]
    return VerbForm()

