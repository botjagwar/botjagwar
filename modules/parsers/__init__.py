# coding: utf8

from inflection_template import EnWiktionaryInflectionTemplateParser

from modules.parsers.functions import parse_inflection_of
from modules.parsers.functions import parse_lv_inflection_of
from modules.parsers.functions import parse_one_parameter_template
from modules.parsers.inflection_template import EnWiktionaryInflectionTemplateParser


CASES = {
    'nom': u'endriky ny lazaina',
    'acc': u'endrika teny fameno',
    'loc': u'endrika teny famaritan-toerana',
    'dat': u'mpanamarika ny tolorana',
    'gen': u'mpanamarika ny an\'ny tompo',
    'ins': u'mpanamarika fomba fanaovana',
}
NUMBER = {
    's': u'singiolary',
    'p': u'ploraly',
}
GENDER = {
    'm': u'andehilahy',
    'f': u'ambehivavy',
    'n': u'tsy miandany'
}

templates_parser = EnWiktionaryInflectionTemplateParser()
templates_parser.add_parser(u'feminine singular of', parse_one_parameter_template(u'feminine singular of', number=u's'))
templates_parser.add_parser(u'feminine plural of', parse_one_parameter_template(u'feminine plural of', number=u'p'))
templates_parser.add_parser(u'feminine of', parse_one_parameter_template(u'feminine of'))
templates_parser.add_parser(u'inflection of', parse_inflection_of)
templates_parser.add_parser(u'inflected form of', parse_one_parameter_template(u'inflected form of'))
templates_parser.add_parser(u'lv-inflection of', parse_lv_inflection_of)
templates_parser.add_parser(u'masculine plural of', parse_one_parameter_template(u'masculine plural of', number=u'p'))
templates_parser.add_parser(u'plural of', parse_one_parameter_template(u'plural of', number=u'p'))


def template_expression_to_malagasy_definition(template_expr):
    """
    :param template_expr: template instance string with all its parameters
    :return: A malagasy language definition in unicode
    """
    word_form = templates_parser.get_elements(template_expr)

    explanation = u''
    if word_form.case in CASES:
        explanation += CASES[word_form.case] + u' '
    if word_form.gender in GENDER:
        explanation += GENDER[word_form.gender] + u' '
    if word_form.number in NUMBER:
        explanation += NUMBER[word_form.number] + u' '

    ret = u'%s ny teny [[%s]]' % (explanation, word_form.lemma)
    return ret


def get_lemma(template_expression):
    return templates_parser.get_lemma(template_expression)