# coding: utf8

from .inflection_template import EnWiktionaryInflectionTemplateParser

from api.parsers.functions.noun_forms import parse_inflection_of
from api.parsers.functions.noun_forms import parse_noun_form_lv_inflection_of
from api.parsers.functions.noun_forms import parse_one_parameter_template
from api.parsers.functions.verb_forms import parse_verb_form_inflection_of
from api.parsers.functions.adjective_forms import parse_adjective_form

from api.parsers.inflection_template import NounForm, VerbForm, AdjectiveForm
from api.parsers.inflection_template import EnWiktionaryInflectionTemplateParser


templates_parser = EnWiktionaryInflectionTemplateParser()

templates_parser.add_parser(AdjectiveForm, 'de-inflected form of', parse_one_parameter_template(AdjectiveForm, 'de-inflected form of', number='', gender=''))
templates_parser.add_parser(AdjectiveForm, 'es-adj form of', parse_adjective_form)
templates_parser.add_parser(AdjectiveForm, 'feminine plural of', parse_one_parameter_template(AdjectiveForm, 'feminine plural of', number='p'))
templates_parser.add_parser(AdjectiveForm, 'feminine singular of', parse_one_parameter_template(AdjectiveForm, 'feminine singular of', number='s'))
templates_parser.add_parser(AdjectiveForm, 'feminine of', parse_one_parameter_template(AdjectiveForm, 'feminine of'))
templates_parser.add_parser(AdjectiveForm, 'inflected form of', parse_one_parameter_template(AdjectiveForm, 'inflected form of', number='', gender=''))
templates_parser.add_parser(AdjectiveForm, 'inflection of', parse_inflection_of(AdjectiveForm))
templates_parser.add_parser(AdjectiveForm, 'it-adj form of', parse_adjective_form)
templates_parser.add_parser(AdjectiveForm, 'masculine plural of', parse_one_parameter_template(AdjectiveForm, 'masculine plural of', number='p', gender='m'))
templates_parser.add_parser(AdjectiveForm, 'pt-adj form of', parse_adjective_form)
templates_parser.add_parser(AdjectiveForm, 'plural of', parse_one_parameter_template(AdjectiveForm, 'plural of', number='p'))
templates_parser.add_parser(NounForm, 'feminine singular of', parse_one_parameter_template(NounForm, 'feminine singular of', number='s'))
templates_parser.add_parser(NounForm, 'feminine plural of', parse_one_parameter_template(NounForm, 'feminine plural of', number='p'))
templates_parser.add_parser(NounForm, 'feminine of', parse_one_parameter_template(NounForm, 'feminine of'))
templates_parser.add_parser(NounForm, 'inflection of', parse_inflection_of(NounForm))
templates_parser.add_parser(NounForm, 'inflected form of', parse_one_parameter_template(NounForm, 'inflected form of'))
templates_parser.add_parser(NounForm, 'lv-inflection of', parse_noun_form_lv_inflection_of)
templates_parser.add_parser(NounForm, 'masculine plural of', parse_one_parameter_template(NounForm, 'masculine plural of', number='p', gender='m'))
templates_parser.add_parser(NounForm, 'plural of', parse_one_parameter_template(NounForm, 'plural of', number='p'))
templates_parser.add_parser(VerbForm, 'inflection of', parse_verb_form_inflection_of)


def get_lemma(expected_class, template_expression):
    return templates_parser.get_lemma(expected_class, template_expression)