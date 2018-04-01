# coding: utf8

from .inflection_template import EnWiktionaryInflectionTemplateParser

from api.parsers.functions import parse_inflection_of
from api.parsers.functions import parse_lv_inflection_of
from api.parsers.functions import parse_one_parameter_template
from api.parsers.inflection_template import EnWiktionaryInflectionTemplateParser


CASES = {
    'nom': 'endriky ny lazaina',
    'acc': 'endrika teny fameno',
    'loc': 'endrika teny famaritan-toerana',
    'dat': 'mpanamarika ny tolorana',
    'gen': 'mpanamarika ny an\'ny tompo',
    'ins': 'mpanamarika fomba fanaovana',
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

templates_parser = EnWiktionaryInflectionTemplateParser()
templates_parser.add_parser('feminine singular of', parse_one_parameter_template('feminine singular of', number='s'))
templates_parser.add_parser('feminine plural of', parse_one_parameter_template('feminine plural of', number='p'))
templates_parser.add_parser('feminine of', parse_one_parameter_template('feminine of'))
templates_parser.add_parser('inflection of', parse_inflection_of)
templates_parser.add_parser('inflected form of', parse_one_parameter_template('inflected form of'))
templates_parser.add_parser('lv-inflection of', parse_lv_inflection_of)
templates_parser.add_parser('masculine plural of', parse_one_parameter_template('masculine plural of', number='p'))
templates_parser.add_parser('plural of', parse_one_parameter_template('plural of', number='p'))


def template_expression_to_malagasy_definition(template_expr):
    """
    :param template_expr: template instance string with all its parameters
    :return: A malagasy language definition in unicode
    """
    word_form = templates_parser.get_elements(template_expr)

    explanation = ''
    if word_form.case in CASES:
        explanation += CASES[word_form.case] + ' '
    if word_form.gender in GENDER:
        explanation += GENDER[word_form.gender] + ' '
    if word_form.number in NUMBER:
        explanation += NUMBER[word_form.number] + ' '

    ret = '%s ny teny [[%s]]' % (explanation, word_form.lemma)
    return ret


def get_lemma(template_expression):
    return templates_parser.get_lemma(template_expression)