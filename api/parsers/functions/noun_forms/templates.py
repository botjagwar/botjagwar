from api.parsers.inflection_template import NounForm


def parse_fi_form_of(template_expression, **context):
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

    lemma = parts[-1] if "=" in parts[1] else parts[1]
    return NounForm(lemma, case, number, "")


def parse_et_form_of(template_expression, **context):
    "{{et-verb form of|t=da|rikastuma}}"
    for char in "{}":
        template_expression = template_expression.replace(char, "")

    parts = template_expression.split("|")
    number = case = None
    for tparam in parts:
        if tparam.startswith("n="):
            number = tparam[2:]
        if tparam.startswith("c="):
            case = tparam[2:]

    lemma = parts[-1] if "=" in parts[1] else parts[1]
    return NounForm(lemma, case, number, "")


def parse_nl_noun_form_of(template_expression, **context):
    "{{nl-noun form of|pl|aanbouwing}}"
    for char in "{}":
        template_expression = template_expression.replace(char, "")

    parts = template_expression.split("|")
    number = "s"
    case = "nom"

    if parts[1] == "pl":
        number = "pl"
    elif parts[1] == "dim":
        case = "dim"
    else:
        case = parts[1]

    lemma = parts[2]
    return NounForm(lemma, case, number, "")


def parse_lt_noun_form(template_expression, **context):
    "{{lt-form-noun|d|s|abatė}}"
    for char in "{}":
        template_expression = template_expression.replace(char, "")

    parts = template_expression.split("|")
    case = parts[1]
    number = parts[2]

    lemma = parts[-1]
    return NounForm(lemma, case, number, "")
