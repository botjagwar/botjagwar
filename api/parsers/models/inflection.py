from api.parsers import renderers


class NonLemma(object):
    renderer = 'non_lemma'

    def __init__(self, lemma=None, case=None, number=None, gender=None):
        self.gender = gender
        self.case = case
        self.lemma = lemma
        self.number = number

    def to_definition(self, language):
        if hasattr(renderers, language):
            renderer_module = getattr(renderers, language)
            if hasattr(renderer_module, 'render_' + self.renderer):
                return getattr(
                    renderer_module,
                    'render_' +
                    self.renderer)(self)
            raise AttributeError(
                f'Renderer function api.parsers.renderers.{language}.{self.renderer} not found!')
        else:
            raise AttributeError(
                f'Module api.parsers.renderers.{language} not found!')

    def to_malagasy_definition(self):
        return self.to_definition('mg')


class Romanization(NonLemma):
    renderer = 'romanization'


class AlternativeSpelling(NonLemma):
    renderer = 'alternative_spelling'


class VerbForm(NonLemma):
    renderer = 'verb_form'
    tense = None
    mood = None
    person = None
    number = None

    def __init__(
            self,
            lemma=None,
            tense=None,
            mood=None,
            person=None,
            number=None,
            case=None,
            gender=None,
            voice='act'):
        super(
            VerbForm,
            self).__init__(
            lemma=lemma,
            number=number,
            case=case,
            gender=gender)
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

    def __init__(
            self,
            lemma=None,
            case=None,
            number=None,
            gender=None,
            definite=None,
            possessive=None):
        super(
            NounForm,
            self).__init__(
            lemma=lemma,
            case=case,
            number=number,
            gender=gender)
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
