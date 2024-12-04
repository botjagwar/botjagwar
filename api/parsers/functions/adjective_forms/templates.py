# coding: utf8
from api.parsers.inflection_template import AdjectiveForm


def parse_adjective_form(template_expression):
    for char in "{}":
        template_expression = template_expression.replace(char, "")
    parts = template_expression.split("|")
    for tparam in parts:
        if tparam.find("=") != -1:
            parts.remove(tparam)
    t_name, lemma, gender, number_ = parts[:4]
    return AdjectiveForm(lemma, "", number_, gender)


def parse_fi_adjective_form_of(template_expression):
    "{{fi-form of|näverrin|case=nominative|pl=plural}}"
    for char in "{}":
        template_expression = template_expression.replace(char, "")

    parts = template_expression.split("|")
    number = case = None
    for tparam in parts:
        if tparam.startswith("pl="):
            number = tparam[3:]
        if tparam.startswith("case="):
            case = tparam[5:]

    if "=" in parts[1]:
        lemma = parts[-1]
    else:
        lemma = parts[1]

    noun_form = AdjectiveForm(lemma, case, number, "")
    return noun_form
