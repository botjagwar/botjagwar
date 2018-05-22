# coding: utf8
from api.parsers.constants import GENDER, CASES, NUMBER, MOOD, TENSE, PERSONS, VOICE, DEFINITENESS


class NonLemma(object):
    def __init__(self, lemma=None, case=None, number=None, gender=None):
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

    def __init__(self, lemma=None, tense=None, mood=None, person=None, number=None, voice='act'):
        super(VerbForm, self).__init__(lemma=lemma, number=number, case=None, gender=None)
        self.voice = voice
        self.tense = tense
        self.mood = mood
        self.person = person

    def to_malagasy_definition(self):
        """
        :return: A malagasy language definition in unicode
        """
        explanation = ''
        if self.person in PERSONS:
            explanation += PERSONS[self.person] + ' '
        if self.number in NUMBER:
            explanation += NUMBER[self.number] + ' '

        explanation += 'ny ' if len(explanation.strip()) != 0 else ''
        if self.mood in MOOD:
            explanation += MOOD[self.mood] + ' '

        if self.tense in TENSE:
            explanation += TENSE[self.tense] + ' '

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
    definite = None

    def __init__(self, lemma=None, case=None, number=None, gender=None, definite=None):
        super(NounForm, self).__init__(lemma=lemma, case=case, number=number, gender=gender)
        self.definite = definite

    def to_malagasy_definition(self):
        """
        :return: A malagasy language definition in unicode
        """
        explanation = ''
        if self.case in CASES:
            explanation += CASES[self.case] + ' '
        if self.gender in GENDER:
            explanation += GENDER[self.gender] + ' '
        if self.number in NUMBER:
            explanation += NUMBER[self.number] + ' '
        if self.definite in DEFINITENESS:
            explanation += DEFINITENESS[self.definite] + ' '

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

    def get_elements(self, expected_class, form_of_definition):
        # fixme: detect several templates on the same line, and raise exception if such case is encountered.
        # current way of parsing template expressions fails spectacularly (InvalidTitle exceptions) in nasty cases:
        # e.g. {{es-verb form of|mood=imp|num=s|pers=2|formal=n|sense=+|ending=ir|venir}} + {{m|es|te||}}.
        # (true story)
        orig_template_expression = form_of_definition
        for c in '{}':
            form_of_definition = form_of_definition.replace(c, '')
        parts = form_of_definition.split('|')
        if (expected_class, parts[0]) in list(self.process_function.keys()):
            ret = self.process_function[(expected_class, parts[0])](form_of_definition)
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
