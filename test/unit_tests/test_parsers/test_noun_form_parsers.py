from unittest import TestCase

from api.parsers.functions.noun_forms import parse_fi_form_of as parse_fi_form_of_noun
from api.parsers.functions.noun_forms import parse_inflection_of
from api.parsers.functions.noun_forms import parse_lt_noun_form
from api.parsers.functions.noun_forms import parse_nl_noun_form_of
from api.parsers.functions.noun_forms import parse_noun_form_lv_inflection_of
from api.parsers.inflection_template import NounForm


class TestAdjectiveFormParsers(TestCase):

    def test_parse_inflection_of_noun_form(self):
        template_expression = '{{inflection of|abdominal||p|lang=es}}'
        func = parse_inflection_of(NounForm)
        output = func(template_expression)
        self.assertIsInstance(output, NounForm)
        self.assertEqual(output.lemma, 'abdominal')
        self.assertEqual(output.number, 'p')

    def test_parse_noun_form_lv_inflection_of(self):
        template_expression = '{{lv-inflection of|bagātīgs|dat|p|f||adj}}'
        output = parse_noun_form_lv_inflection_of(template_expression)
        self.assertIsInstance(output, NounForm)
        self.assertEqual(output.number, 'p')
        self.assertEqual(output.case, 'dat')
        self.assertEqual(output.lemma, 'bagātīgs')

    def test_parse_fi_form_of_noun(self):
        template_expression = '{{fi-form of|näverrin|case=nominative|pl=plural}}'
        output = parse_fi_form_of_noun(template_expression)
        self.assertIsInstance(output, NounForm)
        self.assertEqual(output.case, 'nominative')
        self.assertEqual(output.number, 'plural')
        self.assertEqual(output.lemma, 'näverrin')

    def test_parse_nl_noun_form_of_plural(self):
        template_expression = '{{nl-noun form of|pl|aanbouwing}}'
        output = parse_nl_noun_form_of(template_expression)
        self.assertEqual(output.number, 'pl')
        self.assertEqual(output.lemma, 'aanbouwing')

    def test_parse_nl_noun_form_of_diminutive(self):
        template_expression = '{{nl-noun form of|dim|aanbiedingsfolder}}'
        output = parse_nl_noun_form_of(template_expression)
        self.assertEqual(output.number, 's')
        self.assertEqual(output.case, 'dim')
        self.assertEqual(output.lemma, 'aanbiedingsfolder')

    def test_parse_nl_noun_form_of_genitive(self):
        template_expression = '{{nl-noun form of|gen|land}}'
        output = parse_nl_noun_form_of(template_expression)
        self.assertEqual(output.number, 's')
        self.assertEqual(output.case, 'gen')
        self.assertEqual(output.lemma, 'land')

    def test_parse_lt_noun_form_of(self):
        template_expression = '{{lt-form-noun|d|s|abatė}}'
        output = parse_lt_noun_form(template_expression)
        self.assertEqual(output.number, 's')
        self.assertEqual(output.case, 'd')
        self.assertEqual(output.lemma, 'abatė')
