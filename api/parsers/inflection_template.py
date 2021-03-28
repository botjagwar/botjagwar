# coding: utf8
from api.parsers import renderers


class NonLemma(object):
    renderer = 'noun_form'

    def __init__(self, lemma=None, case=None, number=None, gender=None):
        self.gender = gender
        self.case = case
        self.lemma = lemma
        self.number = number

    def to_definition(self, language):
        if hasattr(renderers, language):
            renderer_module = getattr(renderers, language)
            if hasattr(renderer_module, 'render_' + self.renderer):
                return getattr(renderer_module, 'render_' + self.renderer)(self)
            else:
                raise AttributeError(f'Renderer function api.parsers.renderers.{language}.{self.renderer} not found!')
        else:
            raise AttributeError(f'Module api.parsers.renderers.{language} not found!')


    def to_malagasy_definition(self):
        raise NotImplementedError()


class VerbForm(NonLemma):
    renderer = 'verb_form'
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
        return self.to_definition('mg')


class NounForm(NonLemma):
    renderer = 'noun_form'
    gender = None
    number = None
    case = None
    lemma = None
    definite = None

    def __init__(self, lemma=None, case=None, number=None, gender=None, definite=None, possessive=None):
        super(NounForm, self).__init__(lemma=lemma, case=case, number=number, gender=gender)
        self.definite = definite
        self.possessive = possessive

    def to_malagasy_definition(self):
        return self.to_definition('mg')


class AdjectiveForm(NounForm):
    pass


class ParserError(Exception):
    pass


class ParserNotFoundError(ParserError):
    pass


class EnWiktionaryInflectionTemplateParser(object):
    def __init__(self):
        self.process_function = {}

    def add_parser(self, return_class, template_name, parser_function):
        if (return_class, template_name) in self.process_function:
            raise ParserError("parser already exists for '%s'" % template_name)
        self.process_function[(return_class, template_name)] = parser_function

    def get_elements(self, expected_class, form_of_definition) -> [VerbForm, AdjectiveForm, NounForm]:
        # fixme: detect several templates on the same line, and raise exception if such case is encountered.
        # current way of parsing template expressions fails spectacularly (InvalidTitle exceptions) in nasty cases:
        # e.g. {{es-verb form of|mood=imp|num=s|pers=2|formal=n|sense=+|ending=ir|venir}} + {{m|es|te||}}.
        # (true story)
        orig_template_expression = form_of_definition
        for c in '{}':
            form_of_definition = form_of_definition.replace(c, '')
        parts = form_of_definition.split('|')
        if (expected_class, parts[0]) in list(self.process_function.keys()):
            try:
                ret = self.process_function[(expected_class, parts[0])](form_of_definition)
                if not isinstance(ret, expected_class):
                    raise ParserError("Wrong object returned. Expected %s, got %s" % (
                        expected_class.__name__,
                        ret.__class__.__name__,
                    ))
                return ret
            except ValueError as exc:
                print('ERROR: ', exc)
                raise exc
        else:
            raise ParserNotFoundError('No parser defined for "%s": %s' % (parts[0], orig_template_expression))


    def get_lemma(self, expected_class, template_expression) -> str:
        return self.get_elements(expected_class, template_expression).lemma
