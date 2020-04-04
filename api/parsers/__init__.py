# coding: utf8

from api.parsers.functions import parse_el_form_of
from api.parsers.functions import parse_hu_inflection_of
from api.parsers.functions import parse_inflection_of
from api.parsers.functions import parse_lv_inflection_of
from api.parsers.functions import parse_one_parameter_template
from api.parsers.functions.adjective_forms import parse_adjective_form
from api.parsers.functions.adjective_forms import parse_fi_adjective_form_of
from api.parsers.functions.noun_forms import parse_et_form_of
from api.parsers.functions.noun_forms import parse_fi_form_of as parse_fi_noun_form_of
from api.parsers.functions.noun_forms import parse_lt_noun_form
from api.parsers.functions.noun_forms import parse_nl_noun_form_of
from api.parsers.functions.verb_forms import parse_ca_verb_form_of
from api.parsers.functions.verb_forms import parse_de_verb_form_of
from api.parsers.functions.verb_forms import parse_es_compound_of
from api.parsers.functions.verb_forms import parse_es_verb_form_of
# from api.parsers.functions.verb_forms import parse_ru_participle_of
from api.parsers.functions.verb_forms import parse_fi_form_of
from api.parsers.functions.verb_forms import parse_fi_verb_form_of
from api.parsers.functions.verb_forms import parse_la_verb_form_inflection_of
from api.parsers.functions.verb_forms import parse_verb_form_inflection_of
from api.parsers.inflection_template import EnWiktionaryInflectionTemplateParser
from api.parsers.inflection_template import NounForm, VerbForm, AdjectiveForm
from .inflection_template import EnWiktionaryInflectionTemplateParser

TEMPLATE_TO_OBJECT = {
    'e-ana': NounForm,
    'e-mpam-ana': AdjectiveForm,
    'e-mat': VerbForm,
    'ana': NounForm,
    'mpam-ana': AdjectiveForm,
    'mpam': AdjectiveForm,
    'mat': VerbForm,
}

FORM_OF_TEMPLATE = {
    'ana': 'e-ana',
    'mpam-ana': 'e-mpam-ana',
    'mpam': 'e-mpam-ana',
    'mat': 'e-mat',
}

templates_parser = EnWiktionaryInflectionTemplateParser()

templates_parser.add_parser(AdjectiveForm, 'de-inflected form of', parse_one_parameter_template(AdjectiveForm, 'de-inflected form of', number='', gender=''))
templates_parser.add_parser(AdjectiveForm, 'el-form-of-nounadj', parse_el_form_of(AdjectiveForm))
templates_parser.add_parser(AdjectiveForm, 'es-adj form of', parse_adjective_form)
templates_parser.add_parser(AdjectiveForm, 'feminine plural of',
                            parse_one_parameter_template(AdjectiveForm, 'feminine plural of', gender='f', number='p'))
templates_parser.add_parser(AdjectiveForm, 'feminine singular of',
                            parse_one_parameter_template(AdjectiveForm, 'feminine singular of', gender='f', number='s'))
templates_parser.add_parser(AdjectiveForm, 'feminine of', parse_one_parameter_template(AdjectiveForm, 'feminine of'))
templates_parser.add_parser(AdjectiveForm, 'fi-form of', parse_fi_adjective_form_of)
templates_parser.add_parser(AdjectiveForm, 'lv-inflection of', parse_lv_inflection_of(AdjectiveForm))
templates_parser.add_parser(AdjectiveForm, 'inflected form of', parse_one_parameter_template(AdjectiveForm, 'inflected form of', number='', gender=''))
templates_parser.add_parser(AdjectiveForm, 'inflection of', parse_inflection_of(AdjectiveForm))
templates_parser.add_parser(AdjectiveForm, 'it-adj form of', parse_adjective_form)
templates_parser.add_parser(AdjectiveForm, 'masculine plural of', parse_one_parameter_template(AdjectiveForm, 'masculine plural of', number='p', gender='m'))
templates_parser.add_parser(AdjectiveForm, 'pt-adj form of', parse_adjective_form)
templates_parser.add_parser(AdjectiveForm, 'plural of', parse_one_parameter_template(AdjectiveForm, 'plural of', number='p'))

templates_parser.add_parser(NounForm, 'el-form-of-nounadj', parse_el_form_of(NounForm))
templates_parser.add_parser(NounForm, 'et-nom form of', parse_et_form_of)
templates_parser.add_parser(NounForm, 'feminine singular of', parse_one_parameter_template(NounForm, 'feminine singular of', number='s'))
templates_parser.add_parser(NounForm, 'feminine plural of', parse_one_parameter_template(NounForm, 'feminine plural of', number='p'))
templates_parser.add_parser(NounForm, 'feminine of', parse_one_parameter_template(NounForm, 'feminine of'))
templates_parser.add_parser(NounForm, 'fi-form of', parse_fi_noun_form_of)
templates_parser.add_parser(NounForm, 'genitive plural definite of',
                            parse_one_parameter_template(NounForm, 'genitive plural definite of', number='p',
                                                         case_name='gen', definiteness='definite'))
templates_parser.add_parser(NounForm, 'genitive plural indefinite of',
                            parse_one_parameter_template(NounForm, 'genitive plural indefinite of', number='p',
                                                         case_name='gen', definiteness='indefinite'))
templates_parser.add_parser(NounForm, 'genitive singular definite of',
                            parse_one_parameter_template(NounForm, 'genitive singular definite of', number='s',
                                                         case_name='gen', definiteness='definite'))
templates_parser.add_parser(NounForm, 'genitive singular indefinite of',
                            parse_one_parameter_template(NounForm, 'genitive singular indefinite of', number='s',
                                                         case_name='gen', definiteness='indefinite'))
templates_parser.add_parser(NounForm, 'got-nom form of', parse_el_form_of(NounForm, -1))
templates_parser.add_parser(NounForm, 'inflection of', parse_inflection_of(NounForm))
templates_parser.add_parser(NounForm, 'hu-inflection of', parse_hu_inflection_of)
templates_parser.add_parser(NounForm, 'is-inflection of', parse_inflection_of(NounForm))
templates_parser.add_parser(NounForm, 'inflected form of', parse_one_parameter_template(NounForm, 'inflected form of'))
templates_parser.add_parser(NounForm, 'lt-form-noun', parse_lt_noun_form)
templates_parser.add_parser(NounForm, 'lv-inflection of', parse_lv_inflection_of(NounForm))
templates_parser.add_parser(NounForm, 'masculine plural of', parse_one_parameter_template(NounForm, 'masculine plural of', number='p', gender='m'))
templates_parser.add_parser(NounForm, 'nl-noun form of', parse_nl_noun_form_of)
templates_parser.add_parser(NounForm, 'plural definite of',
                            parse_one_parameter_template(NounForm, 'plural definite of', number='p',
                                                         definiteness='definite'))
templates_parser.add_parser(NounForm, 'plural indefinite of',
                            parse_one_parameter_template(NounForm, 'plural indefinite of', number='p',
                                                         definiteness='indefinite'))
templates_parser.add_parser(NounForm, 'plural of', parse_one_parameter_template(NounForm, 'plural of', number='p'))
templates_parser.add_parser(NounForm, 'singular definite of',
                            parse_one_parameter_template(NounForm, 'singular definite of', number='s',
                                                         definiteness='definite'))
templates_parser.add_parser(NounForm, 'singular indefinite of',
                            parse_one_parameter_template(NounForm, 'singular indefinite of', number='s',
                                                         definiteness='indefinite'))
templates_parser.add_parser(VerbForm, 'ca-verb form of', parse_ca_verb_form_of)
templates_parser.add_parser(VerbForm, 'pt-verb-form-of', parse_one_parameter_template(VerbForm, 'pt-verb-form-of', number='', gender=''))
templates_parser.add_parser(VerbForm, 'de-verb form of', parse_de_verb_form_of)
templates_parser.add_parser(VerbForm, 'es-verb form of', parse_es_verb_form_of)
templates_parser.add_parser(VerbForm, 'fi-verb form of', parse_fi_verb_form_of)
templates_parser.add_parser(VerbForm, 'inflection of', parse_verb_form_inflection_of)
templates_parser.add_parser(VerbForm, 'fi-form of', parse_fi_form_of)
templates_parser.add_parser(VerbForm, 'es-compound of', parse_es_compound_of)
templates_parser.add_parser(VerbForm, 'lv-inflection of', parse_lv_inflection_of(VerbForm))
#templates_parser.add_parser(VerbForm, 'ru-participle of', parse_ru_participle_of)
#templates_parser.add_parser(VerbForm, 'inflection of', parse_inflection_of(VerbForm))


def get_lemma(expected_class, template_expression):
    return templates_parser.get_lemma(expected_class, template_expression)