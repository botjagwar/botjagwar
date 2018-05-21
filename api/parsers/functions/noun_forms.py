from api.parsers.inflection_template import NounForm, CASES, GENDER, NUMBER


def parse_one_parameter_template(out_class, template_name='plural of', case_name='', number='s', gender=None):
    """
    Very generic code that can parse anything like {{plural of|xxyyzz}}, which is very common on en.wiktionary
    Use with caution, though.
    :param out_class:
    :param template_name:
    :param case_name:
    :param number:
    :param gender:
    :return: a function which sould return the contents of the template specified in template_name
    """
    def _parse_one_parameter_template(template_expression):
        for char in '{}':
            template_expression = template_expression.replace(char, '')
        parts = template_expression.split('|')
        lemma = parts[1]
        if parts[0] == template_name:
            return out_class(
                lemma=lemma,
                case=case_name,
                number=number,
                gender=gender)
        else:
            raise ValueError("Unrecognised template: expected '%s' but got '%s'" % (parts[0], template_name))

    return _parse_one_parameter_template


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


def parse_inflection_of(out_class):
    def _parse_inflection_of_partial(template_expression):
        for char in '{}':
            template_expression = template_expression.replace(char, '')
        parts = template_expression.split('|')
        for tparam in parts:
            if tparam.find('=') != -1:
                parts.remove(tparam)
        t_name, lemma = parts[:2]
        case_name = number_ = ''
        gender = None
        for pn in parts:
            if pn in NUMBER:
                number_ = pn
            elif pn in CASES:
                case_name = pn
            elif pn in GENDER:
                gender = pn

        return out_class(lemma=lemma, case=case_name, number=number_, gender=gender)

    return _parse_inflection_of_partial


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
