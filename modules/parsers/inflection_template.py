# coding: utf8

class EnWiktionaryInflectionTemplateParser(object):
    def __init__(self):
        self.process_function = {}

    def add_parser(self, template_name, parser_function):
        self.process_function[template_name] = parser_function

    def get_elements(self, template_expression):
        orig_template_expression = template_expression
        for c in u'{}':
            template_expression = template_expression.replace(c, u'')
        parts = template_expression.split(u'|')
        if parts[0] in self.process_function.keys():
            ret = self.process_function[parts[0]](template_expression)
            assert len(ret) == 4, u'Unexpected return values'
        else:
            raise AttributeError(u'No parser defined for "%s": %s' % (parts[0], orig_template_expression))

        return ret

    def get_lemma(self, template_expression):
        return self.get_elements(template_expression)[1]
