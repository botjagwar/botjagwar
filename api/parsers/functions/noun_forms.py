from api.parsers.inflection_template import NounForm, CASES, GENDER, NUMBER


def parse_noun_form_lv_inflection_of(template_expression):
    """Example of recognised template:
        {{lv-inflection of|bagātīgs|dat|p|f||adj}}
       Should return 4 parameter """
    for char in '{}':
        template_expression = template_expression.replace(char, '')
    parts = template_expression.split('|')
    for tparam in parts:
        if tparam.find('=') != -1:
            parts.remove(tparam)
    lemma = parts[1]
    case_name = number_ = gender = ''
    for pn in parts:
        if pn in NUMBER:
            number_ = pn
        elif pn in CASES:
            case_name = pn
        elif pn in GENDER:
            gender = pn
    return NounForm(lemma, case_name, number_, gender)



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
