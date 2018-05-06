# coding: utf8
from api.parsers.inflection_template import AdjectiveForm


def parse_it_adjective_form(template_expression):
    for char in '{}':
        template_expression = template_expression.replace(char, '')
    parts = template_expression.split('|')
    for tparam in parts:
        if tparam.find('=') != -1:
            parts.remove(tparam)
    t_name, lemma, gender, number_ = parts[:4]
    return AdjectiveForm(lemma, '', number_, gender)
