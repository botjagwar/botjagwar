# coding: utf8

class WordForm(object):
    gender = None
    number = None
    case = None
    lemma = None

    def __init__(self, lemma, case, number, gender):
        self.gender = gender
        self.case = case
        self.lemma = lemma
        self.number = number

    def to_definition(self):
        pass


class EnWiktionaryInflectionTemplateParser(object):
    def __init__(self):
        self.process_function = {}

    def add_parser(self, template_name, parser_function):
        self.process_function[template_name] = parser_function

    def get_elements(self, template_expression):
        orig_template_expression = template_expression
        for c in '{}':
            template_expression = template_expression.replace(c, '')
        parts = template_expression.split('|')
        if parts[0] in list(self.process_function.keys()):
            ret = self.process_function[parts[0]](template_expression)
        else:
            raise AttributeError('No parser defined for "%s": %s' % (parts[0], orig_template_expression))

        return ret

    def get_lemma(self, template_expression):
        return self.get_elements(template_expression).lemma
