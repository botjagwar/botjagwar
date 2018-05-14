from unittest import TestCase

from api.parsers.constants import MOOD, TENSE, NUMBER, PERSONS, VOICE, CASES, GENDER

from api.parsers.functions.noun_forms import parse_inflection_of
from api.parsers.functions.noun_forms import parse_noun_form_lv_inflection_of
from api.parsers.functions.noun_forms import parse_one_parameter_template
from api.parsers.functions.verb_forms import parse_verb_form_inflection_of
from api.parsers.functions.verb_forms import parse_es_verb_form_of
from api.parsers.functions.verb_forms import parse_fi_verb_form_of
from api.parsers.functions.verb_forms import parse_fi_form_of
from api.parsers.functions.adjective_forms import parse_adjective_form

from api.parsers.inflection_template import NounForm, VerbForm, AdjectiveForm


class TestInflectionTemplatesParser(TestCase):
    def test_parse_adjective_form(self):
        template_expression = '{{es-adj form of|minúsculo|f|sg}}'
        output = parse_adjective_form(template_expression)
        self.assertIsInstance(output, AdjectiveForm)
        self.assertEqual(output.number, 'sg')
        self.assertEqual(output.gender, 'f')
        self.assertEqual(output.lemma, 'minúsculo')

    def test_parse_verb_form_inflection_of(self):
        template_expression = '{{inflection of|finalizzare||3|p|cond|lang=it}}'
        output = parse_verb_form_inflection_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, 'p')
        self.assertEqual(output.lemma, 'finalizzare')
        self.assertEqual(output.mood, 'cond')
        self.assertEqual(output.person, '3')

    def test_parse_inflection_of_noun_form(self):
        template_expression = '{{inflection of|abdominal||p|lang=es}}'
        func = parse_inflection_of(NounForm)
        output = func(template_expression)
        self.assertIsInstance(output, NounForm)
        self.assertEqual(output.lemma, 'abdominal')
        self.assertEqual(output.number, 'p')

    def test_parse_inflection_of_adjective_form(self):
        template_expression = '{{inflection of|abdominālis||voc|f|p|lang=la}}'
        func = parse_inflection_of(AdjectiveForm)
        output = func(template_expression)
        self.assertIsInstance(output, AdjectiveForm)
        self.assertEqual(output.lemma, 'abdominālis')
        self.assertEqual(output.number, 'p')
        self.assertEqual(output.gender, 'f')
        self.assertEqual(output.case, 'voc')

    def test_parse_one_parameter_template(self):
        template_expression = '{{feminine singular of|comparatif|lang=fr}}'
        func = parse_one_parameter_template(AdjectiveForm, 'feminine singular of', number='s')
        output = func(template_expression)
        self.assertEqual(output.number, 's')
        self.assertEqual(output.lemma, 'comparatif')

    def test_parse_es_verb_form_of(self):
        template_expression = '{{es-verb form of|person=third-person|number=plural|tense=imperfect|mood=subjunctive|sera=ra|ending=ar|terminar}}'
        output = parse_es_verb_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, 'plural')
        self.assertEqual(output.lemma, 'terminar')
        self.assertEqual(output.tense, 'imperfect')
        self.assertEqual(output.mood, 'subjunctive')
        self.assertEqual(output.person, 'third-person')

        template_expression = '{{es-verb form of|ending=ar|mood=indicative|tense=preterite|pers=1|number=singular|despegar}}'
        output = parse_es_verb_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, 'singular')
        self.assertEqual(output.lemma, 'despegar')
        self.assertEqual(output.tense, 'preterite')
        self.assertEqual(output.mood, 'indicative')
        self.assertEqual(output.person, '1')

        # edge cases (5% of entries)
        template_expression = '{{es-verb form of|ending=ar|mood=indicative|tense=future|pers=2|formal=no|number=plural|ababillarse|region=Spain}}'
        output = parse_es_verb_form_of(template_expression)
        self.assertEqual(output.lemma, 'ababillarse')

    def test_parse_noun_form_lv_inflection_of(self):
        template_expression = '{{lv-inflection of|bagātīgs|dat|p|f||adj}}'
        output = parse_noun_form_lv_inflection_of(template_expression)
        self.assertIsInstance(output, NounForm)
        self.assertEqual(output.number, 'p')
        self.assertEqual(output.case, 'dat')
        self.assertEqual(output.lemma, 'bagātīgs')

    def test_parse_fi_verb_form_of(self):
        template_expression = '{{fi-verb form of|pn=pass|tm=impr|absorboitua}}'
        output = parse_fi_verb_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, 's')
        self.assertEqual(output.tense, 'pres')
        self.assertEqual(output.lemma, 'absorboitua')

    def test_parse_fi_form_of(self):
        template_expression = '{{fi-form of|aateloida|pr=third-person|pl=singular|mood=indicative|tense=present}}'
        output = parse_fi_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.person, 'third-person')
        self.assertEqual(output.number, 'singular')
        self.assertEqual(output.tense, 'present')
        self.assertEqual(output.mood, 'indicative')
        self.assertEqual(output.lemma, 'aateloida')


class TestInflectionTemplateClasses(TestCase):
    def test_NounForm(self):
        obj = NounForm('slk', 'acc', 'p', 'f')
        mg_def = obj.to_malagasy_definition()
        self.assertIn(CASES['acc'], mg_def)
        self.assertIn(NUMBER['p'], mg_def)
        self.assertIn(GENDER['f'], mg_def)

    def test_VerbForm(self):
        obj = VerbForm('alsk', 'pres', 'cond', '1', 'p', 'pass')
        mg_def = obj.to_malagasy_definition()
        self.assertIn(MOOD['cond'], mg_def)
        self.assertIn(PERSONS['1'], mg_def)
        self.assertIn(NUMBER['p'], mg_def)
        self.assertIn(VOICE['pass'], mg_def)
        self.assertIn(TENSE['pres'], mg_def)

    def test_AdjectiveForm(self):
        obj = AdjectiveForm('qpowi', 'acc', 's', 'm')
        mg_def = obj.to_malagasy_definition()
        self.assertIn(CASES['acc'], mg_def)
        self.assertIn(NUMBER['s'], mg_def)
        self.assertIn(GENDER['m'], mg_def)