from unittest import TestCase

from api.parsers.functions.verb_forms import parse_ca_verb_form_of
from api.parsers.functions.verb_forms import parse_de_verb_form_of
from api.parsers.functions.verb_forms import parse_es_verb_form_of
from api.parsers.functions.verb_forms import parse_fi_form_of
from api.parsers.functions.verb_forms import parse_fi_verb_form_of
from api.parsers.functions.verb_forms import parse_verb_form_inflection_of
from api.parsers.inflection_template import VerbForm


class TestAdjectiveFormParsers(TestCase):

    def test_parse_verb_form_inflection_of(self):
        template_expression = '{{inflection of|finalizzare||3|p|cond|lang=it}}'
        output = parse_verb_form_inflection_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, 'p')
        self.assertEqual(output.lemma, 'finalizzare')
        self.assertEqual(output.mood, 'cond')
        self.assertEqual(output.person, '3')

    def test_parse_inflection_of_noun_form_2(self):
        template_expression = '{{inflection of|fr|sursaturer||3|s|simple|futr}}'
        output = parse_verb_form_inflection_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.lemma, 'sursaturer')
        self.assertEqual(output.number, 's')

    def test_parse_ca_verb_form_of(self):
        template_expression = '{{ca-verb form of|p=2|n=sg|t=impf|m=ind|abordar}}'
        output = parse_ca_verb_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.number, 'sg')
        self.assertEqual(output.lemma, 'abordar')
        self.assertEqual(output.tense, 'impf')
        self.assertEqual(output.mood, 'ind')
        self.assertEqual(output.person, '2')

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

    def test_parse_de_verb_form_of(self):
        template_expression = '{{de-verb form of|abfangen|1|s|k2|a}}'
        output = parse_de_verb_form_of(template_expression)
        self.assertIsInstance(output, VerbForm)
        self.assertEqual(output.person, '1')
        self.assertEqual(output.number, 's')
        self.assertEqual(output.tense, '')
        self.assertEqual(output.mood, 'subj')
        self.assertEqual(output.lemma, 'abfangen')