from api.parsers.inflection_template import NounForm


def parse_fi_form_of(template_expression):
    '{{fi-form of|näverrin|case=nominative|pl=plural}}'
    for char in '{}':
        template_expression = template_expression.replace(char, '')

    parts = template_expression.split('|')
    number = case = None
    for tparam in parts:
        if tparam.startswith('pl='):
            number = tparam[3:]
        if tparam.startswith('case='):
            case = tparam[5:]

    if '=' in parts[1]:
        lemma = parts[-1]
    else:
        lemma = parts[1]

    noun_form = NounForm(lemma, case, number, '')
    return noun_form


def parse_et_form_of(template_expression):
    '{{et-verb form of|t=da|rikastuma}}'
    for char in '{}':
        template_expression = template_expression.replace(char, '')

    parts = template_expression.split('|')
    number = case = None
    for tparam in parts:
        if tparam.startswith('n='):
            number = tparam[2:]
        if tparam.startswith('c='):
            case = tparam[2:]

    if '=' in parts[1]:
        lemma = parts[-1]
    else:
        lemma = parts[1]

    noun_form = NounForm(lemma, case, number, '')
    return noun_form


def parse_nl_noun_form_of(template_expression):
    '{{nl-noun form of|pl|aanbouwing}}'
    for char in '{}':
        template_expression = template_expression.replace(char, '')

    parts = template_expression.split('|')
    number = 's'
    case = 'nom'

    if parts[1] == 'pl':
        number = 'pl'
    elif parts[1] == 'dim':
        case = 'dim'
    else:
        case = parts[1]

    lemma = parts[2]
    noun_form = NounForm(lemma, case, number, '')
    return noun_form


def parse_lt_noun_form(template_expression):
    '{{lt-form-noun|d|s|abatė}}'
    for char in '{}':
        template_expression = template_expression.replace(char, '')

    parts = template_expression.split('|')
    case = parts[1]
    number = parts[2]

    lemma = parts[-1]
    noun_form = NounForm(lemma, case, number, '')
    return noun_form
