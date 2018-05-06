# coding: utf8

CASES = {
    'nom': 'endriky ny lazaina',
    'acc': 'endrika teny fameno',
    'loc': 'endrika teny famaritan-toerana',
    'dat': 'mpanamarika ny tolorana',
    'gen': 'mpanamarika ny an\'ny tompo',
    'ins': 'mpanamarika fomba fanaovana',
    'pre': 'endrika mampiankina'
}
NUMBER = {
    's': 'singiolary',
    'p': 'ploraly',
}
GENDER = {
    'm': 'andehilahy',
    'f': 'ambehivavy',
    'n': 'tsy miandany'
}


class VerbForm(object):
    tense = None
    mood = None
    person = None
    number = None

    def __init__(self, tense, mood, person, number):
        self.tense = tense
        self.mood = mood
        self.person = person
        self.number = number


class NounForm(object):
    gender = None
    number = None
    case = None
    lemma = None

    def __init__(self, lemma, case, number, gender):
        self.gender = gender
        self.case = case
        self.lemma = lemma
        self.number = number

    def to_malagasy_definition(self):
        """
        :param template_expr: template instance string with all its parameters
        :return: A malagasy language definition in unicode
        """
        explanation = ''
        if self.case in CASES:
            explanation += CASES[self.case] + ' '
        if self.gender in GENDER:
            explanation += GENDER[self.gender] + ' '
        if self.number in NUMBER:
            explanation += NUMBER[self.number] + ' '

        ret = '%s ny teny [[%s]]' % (explanation, self.lemma)
        return ret


class AdjectiveForm(NounForm):
    pass


class ParserError(Exception):
    pass


class EnWiktionaryInflectionTemplateParser(object):
    def __init__(self):
        self.process_function = {}

    def add_parser(self, return_class, template_name, parser_function):
        if (return_class, template_name) in self.process_function:
            raise ParserError("parser already exists for '%s'" % template_name)
        self.process_function[(return_class, template_name)] = parser_function

    def get_elements(self, expected_class, template_expression):
        orig_template_expression = template_expression
        for c in '{}':
            template_expression = template_expression.replace(c, '')
        parts = template_expression.split('|')
        if (expected_class, parts[0]) in list(self.process_function.keys()):
            ret = self.process_function[(expected_class, parts[0])](template_expression)
            if not isinstance(ret, expected_class):
                raise AttributeError("Wrong object returned. Expected %s, got %s" % (
                    expected_class.__name__,
                    ret.__class__.__name__,
                ))
        else:
            raise AttributeError('No parser defined for "%s": %s' % (parts[0], orig_template_expression))

        return ret

    def get_lemma(self, expected_class, template_expression):
        return self.get_elements(expected_class, template_expression).lemma
