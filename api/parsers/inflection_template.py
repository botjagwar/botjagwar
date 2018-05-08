# coding: utf8
from api.parsers.constants import GENDER, CASES, NUMBER, MOOD, TENSE, PERSONS, VOICE


class NonLemma(object):
    def __init__(self, lemma, case, number, gender):
        self.gender = gender
        self.case = case
        self.lemma = lemma
        self.number = number

    def to_malagasy_definition(self):
        raise NotImplementedError()


class VerbForm(NonLemma):
    tense = None
    mood = None
    person = None
    number = None

    def __init__(self, lemma, tense, mood, person, number, voice='act'):
        super(VerbForm, self).__init__(lemma=lemma, number=number, case=None, gender=None)
        self.voice = voice
        self.tense = tense
        self.mood = mood
        self.person = person

    def to_malagasy_definition(self):
        """
        :param template_expr: template instance string with all its parameters
        :return: A malagasy language definition in unicode
        """
        explanation = ''
        if self.person in PERSONS:
            explanation += PERSONS[self.person] + ' '
        if self.number in NUMBER:
            explanation += NUMBER[self.number] + ' '

        explanation += 'ny ' if len(explanation.strip()) != 0 else ''
        if self.tense in TENSE:
            explanation += TENSE[self.tense] + ' '
        if self.mood in MOOD:
            explanation += MOOD[self.mood] + ' '

        explanation += 'ny ' if len(explanation.strip()) != 0 else ''
        if self.voice in VOICE:
            explanation += VOICE[self.voice] + ' '

        if not explanation.strip():
            explanation = 'endriky'

        ret = '%s ny matoanteny [[%s]]' % (explanation, self.lemma)
        return ret


class NounForm(NonLemma):
    gender = None
    number = None
    case = None
    lemma = None

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

        if not explanation.strip():
            explanation = 'endriky'

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
